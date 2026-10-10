from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from murphyos.web import DemoApplication, StyrAIRequestHandler


class AIGovernanceControlPlaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.application = DemoApplication(
            Path(self.temporary_directory.name) / "ai-governance-audit.jsonl"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def inspect(
        self,
        prompt: str,
        *,
        model_id: str = "corporate-copilot-external",
        classification: str = "internal",
        use_case: str = "knowledge_and_drafting",
    ) -> dict[str, object]:
        return self.application.inspect_ai_prompt(
            {
                "model_id": model_id,
                "actor": "employee-demo",
                "use_case": use_case,
                "classification": classification,
                "prompt": prompt,
            }
        )

    def test_inventory_contains_deployed_finance_healthcare_and_corporate_models(self) -> None:
        state = self.application.ai_governance_state()
        model_ids = {item["model_id"] for item in state["models"]}
        self.assertIn("finance-credit-risk-prod", model_ids)
        self.assertIn("healthcare-summary-prod", model_ids)
        self.assertIn("corporate-copilot-external", model_ids)
        self.assertIn("shadow-consumer-ai", model_ids)
        self.assertEqual(state["enforcement"]["decisions"], [
            "allow",
            "redact",
            "block",
            "route",
        ])
        self.assertFalse(state["enforcement"]["raw_prompts_retained"])

    def test_assessment_flags_control_gap_and_maps_obligations_without_legal_claim(self) -> None:
        result = self.application.assess_ai_model("finance-credit-risk-prod")
        self.assertEqual(result["assessment"]["result"], "action_required")
        self.assertIn("VAL-001", result["policy_breaches"])
        self.assertTrue(result["regulatory_obligations_at_risk"])
        self.assertFalse(result["legal_violation_confirmed"])
        self.assertEqual(result["owner"], "Head of Credit Model Risk")

    def test_approved_benign_prompt_is_allowed(self) -> None:
        result = self.inspect("Summarise the public employee travel policy.")
        self.assertEqual(result["decision"], "allow")
        self.assertTrue(result["provider_invoked"])
        self.assertTrue(result["external_provider_invoked"])
        self.assertIsNone(result["incident"])
        self.assertFalse(result["raw_input_stored"])

    def test_confidential_identifiers_are_redacted_before_external_provider(self) -> None:
        raw_email = "alex.unique982@example.test"
        raw_account = "NO93 8601 1117 947"
        result = self.inspect(
            f"Draft a confidential reply to {raw_email} about {raw_account}.",
            classification="confidential",
        )
        self.assertEqual(result["decision"], "redact")
        self.assertTrue(result["provider_invoked"])
        self.assertIn("[REDACTED EMAIL]", result["provider_payload"])
        self.assertIn("[REDACTED BANK ACCOUNT]", result["provider_payload"])
        self.assertNotIn(raw_email, result["provider_payload"])
        self.assertNotIn(raw_account, result["provider_payload"])
        audit_json = json.dumps(self.application.service.audit_log.records())
        self.assertNotIn(raw_email, audit_json)
        self.assertNotIn(raw_account, audit_json)

    def test_restricted_data_is_prevented_at_external_boundary_and_routed(self) -> None:
        result = self.inspect(
            "patient_id=PAT-DEMO-204 needs a summary for clinical review.",
            classification="confidential",
        )
        self.assertEqual(result["decision"], "route")
        self.assertEqual(result["routed_to"], "secure-enterprise-llm")
        self.assertTrue(result["provider_invoked"])
        self.assertFalse(result["external_provider_invoked"])
        self.assertTrue(result["event"]["transmission_prevented"])
        self.assertIn("[REDACTED CLINICAL ID]", result["provider_payload"])
        self.assertEqual(
            result["destination_trust"]["effective_provider"],
            "Customer-controlled private inference",
        )

    def test_secret_is_blocked_and_creates_incident_finding_and_evidence(self) -> None:
        secret = "fictional-secret-value-8271"
        result = self.inspect(f"api_key={secret}")
        self.assertEqual(result["decision"], "block")
        self.assertFalse(result["provider_invoked"])
        self.assertIsNone(result["provider_payload"])
        self.assertIsNotNone(result["incident"])
        self.assertIsNotNone(result["finding"])
        evidence = self.application.ai_governance_evidence(result["evidence_id"])
        self.assertEqual(evidence["schema"], "styrai.ai-governance-evidence.v1")
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["related_incidents"])
        self.assertTrue(evidence["related_findings"])
        self.assertNotIn(secret, json.dumps(evidence))

    def test_shadow_ai_and_out_of_scope_use_fail_closed(self) -> None:
        shadow = self.inspect(
            "Public demonstration content.",
            model_id="shadow-consumer-ai",
            classification="public",
            use_case="unknown",
        )
        self.assertEqual(shadow["decision"], "block")
        self.assertFalse(shadow["provider_invoked"])

        wrong_use = self.inspect(
            "Decide whether this person receives a loan.",
            use_case="autonomous_credit_decision",
        )
        self.assertEqual(wrong_use["decision"], "block")
        self.assertIn("approved purpose", wrong_use["event"]["reason"])

    def test_drift_threshold_guards_model_routes_traffic_and_maps_policy(self) -> None:
        result = self.application.monitor_ai_model(
            "finance-credit-risk-prod",
            {"metric": "drift_score", "value": 0.29},
        )
        self.assertTrue(result["monitoring_event"]["breached"])
        self.assertEqual(result["policy_breach"], "MON-001")
        self.assertEqual(result["containment_status"], "guarded_and_routed")
        self.assertEqual(result["model"]["status"], "guarded")
        self.assertIsNotNone(result["incident"])
        self.assertIsNotNone(result["finding"])
        self.assertEqual(result["before_metrics"]["drift_score"], 0.06)
        self.assertEqual(result["after_metrics"]["drift_score"], 0.29)
        self.assertFalse(result["legal_violation_confirmed"])

    def test_unapproved_version_change_is_contained_and_evidenced(self) -> None:
        result = self.application.observe_ai_model_version(
            "healthcare-summary-prod",
            {"observed_version": "2026.09-unreviewed"},
        )
        self.assertFalse(result["version_event"]["matched"])
        self.assertEqual(result["policy_breach"], "USE-001")
        self.assertEqual(result["containment_status"], "version_mismatch_contained")
        self.assertEqual(result["model"]["status"], "guarded")
        evidence = self.application.ai_governance_evidence(result["evidence_id"])
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertTrue(evidence["related_findings"])
        self.assertTrue(evidence["related_incidents"])

    def test_finding_remediation_requires_owner_and_rationale(self) -> None:
        finding_id = self.application.ai_governance_state()["findings"][0][
            "finding_id"
        ]
        with self.assertRaises(ValueError):
            self.application.resolve_ai_finding(finding_id, {"owner": "Model Risk"})
        resolved = self.application.resolve_ai_finding(
            finding_id,
            {
                "owner": "Model Risk",
                "rationale": "Synthetic evidence reviewed and control restored.",
            },
        )
        self.assertEqual(resolved["status"], "remediated")
        self.assertTrue(self.application.service.audit_log.verify())


class AIGovernanceHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.application = DemoApplication(
            Path(self.temporary_directory.name) / "ai-governance-http-audit.jsonl"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def handler(
        self, path: str, payload: dict[str, object] | None = None
    ) -> StyrAIRequestHandler:
        application = self.application

        class CapturingHandler(StyrAIRequestHandler):
            def __init__(self) -> None:
                self.application = application
                self.path = path
                self.sent: object | None = None
                self.status: object | None = None

            def _read_json(self) -> dict[str, object]:
                return payload or {}

            def _send_json(self, body: object, status: object = 200) -> None:
                self.sent = body
                self.status = status

            def send_error(self, code: object, message: object = None) -> None:
                self.sent = {"error": str(message or code)}
                self.status = code

        return CapturingHandler()

    def test_governance_state_and_inspection_endpoints_execute(self) -> None:
        get_handler = self.handler("/api/governance")
        get_handler.do_GET()
        state = get_handler.sent
        self.assertGreaterEqual(state["metrics"]["deployed_models"], 4)

        post_handler = self.handler(
            "/api/governance/inspect",
            {
                "model_id": "corporate-copilot-external",
                "actor": "http-test-user",
                "use_case": "knowledge_and_drafting",
                "classification": "internal",
                "prompt": "api_key=http-test-secret",
            },
        )
        post_handler.do_POST()
        result = post_handler.sent
        self.assertEqual(result["decision"], "block")
        self.assertFalse(result["provider_invoked"])


if __name__ == "__main__":
    unittest.main()
