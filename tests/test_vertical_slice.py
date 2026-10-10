from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from murphyos.audit import AuditIntegrityError, HashChainedAuditLog
from murphyos.demo import demo_policy
from murphyos.models import ActionRequest, ActionStatus, Decision
from murphyos.policy import PolicyEngine
from murphyos.registry import ModelPassport, ModelPassportRegistry
from murphyos.service import GovernanceService, GovernanceWorkflowError
from murphyos.web import DemoApplication


class GovernanceVerticalSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.audit_path = Path(self.temporary_directory.name) / "audit.jsonl"
        self.audit = HashChainedAuditLog(self.audit_path)
        self.service = GovernanceService(PolicyEngine(demo_policy()), self.audit)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def action(
        *, tool: str, operation: str, classification: str
    ) -> ActionRequest:
        return ActionRequest(
            agent_id="test-agent",
            on_behalf_of="test-user",
            tool=tool,
            operation=operation,
            resource="test-resource",
            resource_classification=classification,
        )

    def test_explicit_safe_read_is_authorized(self) -> None:
        result = self.service.propose(
            self.action(tool="documents", operation="read", classification="internal")
        )
        self.assertEqual(result.decision.effect, Decision.ALLOW)
        self.assertEqual(result.status, ActionStatus.AUTHORIZED)
        self.assertTrue(result.authorization_receipt.startswith("styrai_receipt_v1_"))
        self.assertTrue(self.audit.verify())

    def test_external_email_waits_for_approval(self) -> None:
        result = self.service.propose(
            self.action(tool="email", operation="send_external", classification="internal")
        )
        self.assertEqual(result.status, ActionStatus.WAITING_APPROVAL)
        approved = self.service.decide_approval(
            result.request.action_id,
            approver_id="manager",
            approved=True,
            rationale="Approved test action.",
        )
        self.assertEqual(approved.status, ActionStatus.AUTHORIZED)
        self.assertEqual(approved.approved_by, ["manager"])
        self.assertTrue(self.audit.verify())

    def test_material_financial_payment_requires_two_distinct_approvers(self) -> None:
        result = self.service.propose(
            ActionRequest(
                agent_id="payments-agent",
                on_behalf_of="operator",
                tool="payments",
                operation="release",
                resource="batch-22",
                resource_classification="restricted",
                industry="financial_services",
                use_case="payment_operations",
                model_id="approved-model",
                model_version="1.0",
                risk_attributes={"amount": 250_000, "currency": "NOK"},
            )
        )
        self.assertEqual(result.decision.required_approvals, 2)
        first = self.service.decide_approval(
            result.request.action_id,
            approver_id="manager-one",
            approved=True,
            rationale="First-line review complete.",
        )
        self.assertEqual(first.status, ActionStatus.WAITING_APPROVAL)
        second = self.service.decide_approval(
            result.request.action_id,
            approver_id="manager-two",
            approved=True,
            rationale="Independent control review complete.",
        )
        self.assertEqual(second.status, ActionStatus.AUTHORIZED)
        self.assertEqual(second.approved_by, ["manager-one", "manager-two"])
        self.assertTrue(second.authorization_receipt)

    def test_approver_must_be_distinct_from_initiator_and_prior_approvers(self) -> None:
        result = self.service.propose(
            ActionRequest(
                agent_id="payments-agent",
                on_behalf_of="operator",
                tool="payments",
                operation="release",
                resource="batch-22",
                resource_classification="restricted",
                industry="financial_services",
                risk_attributes={"amount": 250_000},
            )
        )
        with self.assertRaises(GovernanceWorkflowError):
            self.service.decide_approval(
                result.request.action_id,
                approver_id="operator",
                approved=True,
                rationale="Self approval.",
            )
        self.service.decide_approval(
            result.request.action_id,
            approver_id="manager-one",
            approved=True,
            rationale="First review.",
        )
        with self.assertRaises(GovernanceWorkflowError):
            self.service.decide_approval(
                result.request.action_id,
                approver_id="manager-one",
                approved=True,
                rationale="Duplicate review.",
            )

    def test_restricted_external_email_is_denied_before_approval_rule(self) -> None:
        result = self.service.propose(
            self.action(
                tool="email", operation="send_external", classification="restricted"
            )
        )
        self.assertEqual(result.decision.rule_id, "deny-restricted-external-send")
        self.assertEqual(result.status, ActionStatus.DENIED)

    def test_unmatched_action_fails_closed(self) -> None:
        result = self.service.propose(
            self.action(tool="payments", operation="pay", classification="internal")
        )
        self.assertEqual(result.decision.rule_id, "default")
        self.assertEqual(result.status, ActionStatus.DENIED)

    def test_approval_requires_rationale(self) -> None:
        result = self.service.propose(
            self.action(tool="email", operation="send_external", classification="internal")
        )
        with self.assertRaises(GovernanceWorkflowError):
            self.service.decide_approval(
                result.request.action_id,
                approver_id="manager",
                approved=True,
                rationale="   ",
            )

    def test_authorization_receipt_rejects_a_changed_action_payload(self) -> None:
        request = ActionRequest(
            agent_id="test-agent",
            on_behalf_of="test-user",
            tool="email",
            operation="send_external",
            resource="recipient@example.test",
            resource_classification="internal",
            parameters={"content": "Approved fictional message."},
        )
        result = self.service.propose(request)
        self.service.decide_approval(
            result.request.action_id,
            approver_id="manager",
            approved=True,
            rationale="Approved the exact fictional message.",
        )
        result.request.parameters["content"] = "Changed after approval."
        with self.assertRaises(GovernanceWorkflowError):
            self.service.assert_authorized(result.request.action_id)

    def test_audit_tampering_is_detected(self) -> None:
        self.service.propose(
            self.action(tool="documents", operation="read", classification="internal")
        )
        lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[0])
        record["payload"]["agent_id"] = "tampered-agent"
        lines[0] = json.dumps(record, sort_keys=True)
        self.audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaises(AuditIntegrityError):
            self.audit.verify()

    def test_registered_model_is_constrained_to_approved_use_and_tools(self) -> None:
        registry = ModelPassportRegistry(
            version="test-registry-1",
            passports=(
                ModelPassport(
                    model_id="registered-model",
                    version="1.0",
                    provider="test-provider",
                    owner="model-owner",
                    risk_tier="medium",
                    intended_uses=("document_support",),
                    allowed_tools=("documents",),
                    allowed_classifications=("internal",),
                ),
            ),
        )
        service = GovernanceService(PolicyEngine(demo_policy()), self.audit, registry)
        result = service.propose(
            ActionRequest(
                agent_id="test-agent",
                on_behalf_of="test-user",
                tool="email",
                operation="send_external",
                resource="recipient@example.test",
                resource_classification="internal",
                industry="financial_services",
                use_case="customer_communication",
                model_id="registered-model",
                model_version="1.0",
            )
        )
        self.assertEqual(result.status, ActionStatus.DENIED)
        self.assertEqual(result.decision.rule_id, "model-passport:unapproved_use_case")

    def test_unregistered_model_fails_closed_when_registry_is_enforced(self) -> None:
        registry = ModelPassportRegistry(version="empty-registry", passports=())
        service = GovernanceService(PolicyEngine(demo_policy()), self.audit, registry)
        result = service.propose(
            self.action(tool="documents", operation="read", classification="internal")
        )
        self.assertEqual(result.status, ActionStatus.DENIED)
        self.assertEqual(result.decision.rule_id, "model-passport:model_not_registered")


class CustomerDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.application = DemoApplication(
            Path(self.temporary_directory.name) / "web-audit.jsonl"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_seeded_demo_has_all_three_decision_outcomes(self) -> None:
        state = self.application.state()
        self.assertTrue(state["audit"]["valid"])
        statuses = {action["status"] for action in state["actions"]}
        self.assertEqual(statuses, {"authorized", "waiting_approval", "denied"})

    def test_material_payment_evidence_contains_two_approvals_and_receipt(self) -> None:
        proposed = self.application.propose({"scenario": "material_payment"})
        action_id = proposed["action"]["action_id"]
        self.application.approve(
            action_id,
            {
                "approver_id": "risk-manager",
                "approved": True,
                "rationale": "Risk review complete.",
            },
        )
        approved = self.application.approve(
            action_id,
            {
                "approver_id": "financial-controller",
                "approved": True,
                "rationale": "Independent control complete.",
            },
        )
        evidence = self.application.evidence(action_id)
        self.assertEqual(approved["status"], "authorized")
        self.assertEqual(approved["approvals_received"], 2)
        self.assertTrue(approved["authorization_receipt"])
        self.assertTrue(evidence["audit_chain_valid"])


class ContinuousGovernancePlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.application = DemoApplication(
            Path(self.temporary_directory.name) / "platform-audit.jsonl"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def model_call(
        self,
        prompt: str,
        *,
        asset_id: str = "agent-client-service",
        classification: str = "internal",
    ) -> dict[str, object]:
        return self.application.simulate_model_call(
            {
                "asset_id": asset_id,
                "actor": "test-advisor",
                "classification": classification,
                "prompt": prompt,
            }
        )

    def test_platform_starts_with_inventory_monitoring_and_open_incident(self) -> None:
        state = self.application.platform_state()
        self.assertEqual(state["metrics"]["ai_systems"], 6)
        self.assertEqual(state["metrics"]["production_systems"], 5)
        self.assertEqual(state["metrics"]["monitoring_coverage"], 100)
        self.assertGreaterEqual(state["metrics"]["open_incidents"], 1)
        self.assertTrue(state["audit"]["valid"])
        self.assertFalse(state["data_protection"]["raw_prompts_retained"])

    def test_safe_approved_model_call_is_allowed_and_evidenced(self) -> None:
        result = self.model_call("Summarise the standard mortgage procedure.")
        self.assertEqual(result["event"]["decision"], "allowed")
        self.assertFalse(result["raw_input_stored"])
        self.assertIn("MODEL-USE-02", result["event"]["controls_applied"])
        self.assertTrue(self.application.service.audit_log.verify())

    def test_confidential_external_call_is_redacted_without_raw_prompt_evidence(self) -> None:
        raw_prompt = (
            "Customer cassie.unique847@example.test asks about account "
            "NO93 8601 1117 947. This is confidential."
        )
        result = self.model_call(raw_prompt, classification="confidential")
        event = result["event"]
        self.assertEqual(event["decision"], "allow_with_redaction")
        self.assertIn("email_address", event["detected_data_types"])
        self.assertIn("iban_or_account", event["detected_data_types"])
        self.assertIn("[REDACTED EMAIL]", event["redacted_preview"])
        self.assertIn("[REDACTED ACCOUNT]", event["redacted_preview"])
        audit_json = json.dumps(self.application.service.audit_log.records())
        self.assertNotIn("cassie.unique847@example.test", audit_json)
        self.assertNotIn("NO93 8601 1117 947", audit_json)
        self.assertTrue(self.application.service.audit_log.verify())

    def test_secret_is_blocked_and_automated_incident_is_created(self) -> None:
        result = self.model_call("api_key=fictional-demo-secret")
        self.assertEqual(result["event"]["decision"], "blocked")
        self.assertEqual(result["event"]["effective_classification"], "restricted")
        self.assertIsNotNone(result["incident"])
        state = self.application.platform_state()
        self.assertEqual(state["automation_runs"][0]["rule_id"], "AUTO-DLP")
        self.assertIn("Prevented transmission", result["incident"]["automated_actions"])

    def test_healthcare_identifier_detection_avoids_plain_language_false_positives(self) -> None:
        safe = self.model_call(
            "Direct patient identifiers were removed from this fictional summary.",
            asset_id="agent-healthcare-visit-summary",
            classification="confidential",
        )
        self.assertEqual(safe["event"]["decision"], "allowed")
        self.assertNotIn(
            "healthcare_patient_identifier", safe["event"]["detected_data_types"]
        )

        identified = self.model_call(
            "MRN: MRN-DEMO-204 is a fictional demonstration identifier.",
            asset_id="agent-healthcare-visit-summary",
            classification="confidential",
        )
        self.assertIn(
            "healthcare_patient_identifier",
            identified["event"]["detected_data_types"],
        )
        self.assertIn("[REDACTED PATIENT ID]", identified["event"]["redacted_preview"])

    def test_shadow_ai_destination_fails_closed(self) -> None:
        result = self.model_call(
            "Only fictional public demonstration text.",
            asset_id="shadow-public-ai",
            classification="public",
        )
        self.assertEqual(result["event"]["decision"], "blocked")
        self.assertIn("not approved", result["event"]["reason"])

    def test_health_breach_activates_guardrail_and_validation_workflow(self) -> None:
        result = self.application.simulate_health_breach(
            "model-claims-summary", {"breach": "drift"}
        )
        self.assertEqual(result["asset"]["status"], "guarded")
        self.assertEqual(result["asset"]["health"]["status"], "degraded")
        self.assertGreater(result["asset"]["health"]["drift_score"], 0.15)
        self.assertEqual(result["automation_run"]["rule_id"], "AUTO-DRIFT")
        self.assertEqual(result["incident"]["category"], "model_monitoring")

    def test_silent_model_version_change_is_paused_for_revalidation(self) -> None:
        result = self.application.simulate_version_change("agent-payment-ops")
        self.assertEqual(result["asset"]["status"], "review_required")
        self.assertEqual(result["asset"]["health"]["status"], "paused")
        self.assertNotEqual(
            result["asset"]["version"], result["asset"]["approved_version"]
        )
        self.assertEqual(result["automation_run"]["rule_id"], "AUTO-VERSION")
        self.assertIn("Paused write-capable actions", result["incident"]["automated_actions"])

    def test_evidence_automation_produces_verified_export(self) -> None:
        result = self.application.run_automation("AUTO-EVIDENCE")
        pack_id = result["run"]["related_object"]
        evidence = self.application.evidence_pack(pack_id)
        self.assertEqual(evidence["schema"], "styrai.governance-evidence.v1")
        self.assertEqual(evidence["pack"]["status"], "verified")
        self.assertTrue(evidence["pack"]["audit_chain_valid"])
        self.assertEqual(len(evidence["controls"]), 8)
        self.assertTrue(self.application.service.audit_log.verify())

    def test_incident_resolution_is_hash_chained(self) -> None:
        incident_id = self.application.platform_state()["incidents"][0]["incident_id"]
        resolved = self.application.resolve_incident(incident_id)
        self.assertEqual(resolved["status"], "resolved")
        event_types = {
            record["event_type"] for record in self.application.service.audit_log.records()
        }
        self.assertIn("incident.resolved", event_types)
        self.assertTrue(self.application.service.audit_log.verify())


class EndToEndExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.application = DemoApplication(
            Path(self.temporary_directory.name) / "execution-audit.jsonl"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def start_customer_reply(self) -> dict[str, object]:
        return self.application.start_execution({"scenario": "customer_reply"})

    def approve(self, run_id: str) -> dict[str, object]:
        return self.application.decide_execution(
            run_id,
            {
                "approver_id": "service-manager-demo",
                "approved": True,
                "rationale": "Reviewed the fictional response and secure-channel advice.",
            },
        )

    def test_confidential_task_reaches_approval_with_redacted_provider_payload(self) -> None:
        run = self.start_customer_reply()
        self.assertEqual(run["status"], "waiting_approval")
        self.assertEqual(run["runtime_result"]["decision"], "allow_with_redaction")
        self.assertIn("email_address", run["runtime_result"]["detected_data_types"])
        self.assertIn("iban_or_account", run["runtime_result"]["detected_data_types"])
        self.assertIn("[REDACTED EMAIL]", run["runtime_result"]["provider_payload"])
        self.assertIn("[REDACTED ACCOUNT]", run["runtime_result"]["provider_payload"])
        self.assertFalse(run["runtime_result"]["raw_input_stored"])
        self.assertNotIn("account", run["source_application"])
        self.assertEqual(run["governed_action"]["status"], "waiting_approval")
        self.assertEqual(
            run["governed_action"]["decision"]["rule_id"],
            "approve-external-email",
        )

    def test_execution_is_impossible_before_approval(self) -> None:
        run = self.start_customer_reply()
        with self.assertRaises(ValueError):
            self.application.execute_run(run["run_id"])
        event_types = [
            record["event_type"] for record in self.application.service.audit_log.records()
        ]
        self.assertNotIn("tool.execution_simulated", event_types)

    def test_initiator_cannot_approve_own_execution(self) -> None:
        run = self.start_customer_reply()
        with self.assertRaises(GovernanceWorkflowError):
            self.application.decide_execution(
                run["run_id"],
                {
                    "approver_id": "advisor-demo",
                    "approved": True,
                    "rationale": "Attempted self approval.",
                },
            )

    def test_approved_task_executes_once_with_bound_receipts(self) -> None:
        run = self.start_customer_reply()
        authorised = self.approve(run["run_id"])
        self.assertEqual(authorised["status"], "authorized")
        authorization_receipt = authorised["governed_action"][
            "authorization_receipt"
        ]
        self.assertTrue(authorization_receipt.startswith("styrai_receipt_v1_"))
        executed = self.application.execute_run(run["run_id"])
        repeated = self.application.execute_run(run["run_id"])
        self.assertEqual(executed["status"], "executed")
        self.assertEqual(executed["delivery"]["outcome"], "simulated_delivered")
        self.assertFalse(executed["delivery"]["external_side_effect"])
        self.assertEqual(
            executed["delivery"]["authorization_receipt"], authorization_receipt
        )
        self.assertEqual(
            repeated["delivery"]["delivery_receipt"],
            executed["delivery"]["delivery_receipt"],
        )
        event_types = [
            record["event_type"] for record in self.application.service.audit_log.records()
        ]
        self.assertIn("model.draft_generated", event_types)
        self.assertIn("approval.granted", event_types)
        self.assertIn("action.authorized", event_types)
        self.assertEqual(event_types.count("tool.execution_simulated"), 1)

    def test_blocked_public_ai_attempt_never_invokes_model_or_tool(self) -> None:
        run = self.application.start_execution({"scenario": "public_ai_paste"})
        self.assertEqual(run["status"], "blocked")
        self.assertEqual(run["runtime_result"]["decision"], "blocked")
        self.assertIn("api_secret", run["runtime_result"]["detected_data_types"])
        self.assertIsNotNone(run["runtime_result"]["incident_id"])
        self.assertIsNotNone(run["runtime_result"]["automation_run_id"])
        self.assertIsNone(run["model_output"])
        self.assertIsNone(run["governed_action"])
        self.assertIsNone(run["delivery"])
        audit_json = json.dumps(self.application.service.audit_log.records())
        self.assertNotIn("fictional-demo-secret", audit_json)
        self.assertNotIn("NO93 8601 1117 947", audit_json)

    def test_execution_evidence_correlates_runtime_action_and_delivery(self) -> None:
        run = self.start_customer_reply()
        self.approve(run["run_id"])
        self.application.execute_run(run["run_id"])
        evidence = self.application.execution_evidence(run["run_id"])
        self.assertEqual(evidence["schema"], "styrai.execution-evidence.v1")
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertIsNone(evidence["run"]["model_output"])
        self.assertIsNone(evidence["run"]["runtime_result"]["provider_payload"])
        self.assertNotIn(
            self.application.execution.SAFE_MODEL_OUTPUT, json.dumps(evidence)
        )
        event_types = {record["event_type"] for record in evidence["audit_records"]}
        self.assertIn("runtime.call_evaluated", event_types)
        self.assertIn("policy.decided", event_types)
        self.assertIn("approval.granted", event_types)
        self.assertIn("tool.execution_simulated", event_types)

    def test_platform_reset_clears_execution_run(self) -> None:
        self.start_customer_reply()
        self.application.reset()
        self.assertIsNone(self.application.execution_state()["latest_run"])


if __name__ == "__main__":
    unittest.main()
