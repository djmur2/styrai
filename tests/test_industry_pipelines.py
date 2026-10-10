from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from murphyos.industry_pipelines import PipelineService, PipelineWorkflowError
from murphyos.service import GovernanceWorkflowError
from murphyos.web import DemoApplication


class IndustryPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.application = DemoApplication(
            Path(self.temporary_directory.name) / "pipeline-audit.jsonl"
        )
        self.pipelines = PipelineService(
            self.application.service, self.application.platform
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_catalog_contains_executable_finance_and_healthcare_options(self) -> None:
        state = self.pipelines.state()
        self.assertEqual(
            {item["pipeline_id"] for item in state["catalog"]},
            {"finance-material-payment", "healthcare-visit-summary"},
        )
        for pipeline in state["catalog"]:
            self.assertGreaterEqual(len(pipeline["cases"]), 2)
            self.assertEqual(len(pipeline["stages"]), 8)
            self.assertTrue(pipeline["simulation"]["governance_path_live"])
            self.assertFalse(pipeline["simulation"]["external_tool_connected"])

    def test_finance_happy_path_requires_two_approvals_and_executes_once(self) -> None:
        run = self.pipelines.start(
            {
                "pipeline_id": "finance-material-payment",
                "case_id": "FIN-PAY-8842",
                "run_to_review": True,
            }
        )
        self.assertEqual(run["status"], "waiting_approval")
        self.assertEqual(
            run["governed_action"]["decision"]["required_approvals"], 2
        )
        first = self.pipelines.decide(
            run["run_id"],
            "payments-manager-demo",
            True,
            "The reconciled fictional batch is ready for second-line review.",
        )
        self.assertEqual(first["status"], "waiting_approval")
        authorized = self.pipelines.decide(
            run["run_id"],
            "treasury-controller-demo",
            True,
            "Independent four-eyes review completed.",
        )
        self.assertEqual(authorized["status"], "authorized")
        executed = self.pipelines.execute(run["run_id"])
        repeated = self.pipelines.execute(run["run_id"])
        self.assertEqual(executed["status"], "executed")
        self.assertEqual(executed["reconciliation"]["status"], "matched")
        self.assertEqual(executed["case"]["status"], "released_simulated")
        self.assertEqual(
            repeated["execution"]["adapter_receipt"],
            executed["execution"]["adapter_receipt"],
        )
        event_types = [
            record["event_type"]
            for record in self.application.service.audit_log.records()
        ]
        self.assertEqual(event_types.count("pipeline.tool_executed"), 1)

    def test_completed_finance_fixture_can_be_replayed_without_server_reset(self) -> None:
        def execute_finance_run() -> dict[str, object]:
            run = self.pipelines.start(
                {
                    "pipeline_id": "finance-material-payment",
                    "case_id": "FIN-PAY-8842",
                    "run_to_review": True,
                }
            )
            self.pipelines.decide(
                run["run_id"],
                "payments-manager-demo",
                True,
                "First-line review completed.",
            )
            self.pipelines.decide(
                run["run_id"],
                "treasury-controller-demo",
                True,
                "Independent second-line review completed.",
            )
            return self.pipelines.execute(run["run_id"])

        first = execute_finance_run()
        second = execute_finance_run()

        self.assertEqual(first["status"], "executed")
        self.assertEqual(second["status"], "executed")
        self.assertEqual(
            second["execution"]["before_record"]["operational_status"],
            "held_for_ai_review",
        )
        self.assertEqual(second["execution"]["before_version"], 1)
        self.assertNotEqual(first["run_id"], second["run_id"])

    def test_healthcare_happy_path_requires_clinician_and_reconciles_ehr(self) -> None:
        run = self.pipelines.start(
            {
                "pipeline_id": "healthcare-visit-summary",
                "case_id": "HC-VISIT-204",
                "run_to_review": True,
            }
        )
        self.assertEqual(run["status"], "waiting_approval")
        self.assertEqual(
            run["governed_action"]["decision"]["rule_id"],
            "approve-healthcare-visit-summary",
        )
        with self.assertRaises(PipelineWorkflowError):
            self.pipelines.decide(
                run["run_id"],
                "payments-manager-demo",
                True,
                "Wrong industry reviewer.",
            )
        authorized = self.pipelines.decide(
            run["run_id"],
            "attending-clinician-demo",
            True,
            "The summary is supported by the fictional encounter.",
        )
        self.assertEqual(authorized["status"], "authorized")
        executed = self.pipelines.execute(run["run_id"])
        self.assertEqual(executed["status"], "executed")
        self.assertEqual(executed["reconciliation"]["status"], "matched")
        self.assertEqual(
            executed["execution"]["after_record"]["operational_status"],
            "summary_signed_simulated",
        )
        self.assertEqual(
            executed["execution"]["after_record"]["portal_queue"][0]["status"],
            "queued_simulated",
        )

    def test_finance_amount_mismatch_is_blocked_after_model_before_action(self) -> None:
        run = self.pipelines.start(
            {
                "pipeline_id": "finance-material-payment",
                "mode": "mismatch",
                "run_to_review": True,
            }
        )
        self.assertEqual(run["status"], "blocked")
        self.assertTrue(run["provider_invoked"])
        self.assertFalse(run["downstream_invoked"])
        self.assertIn(
            "amount_matches_authoritative_batch",
            run["validation"]["failure_codes"],
        )
        self.assertIsNone(run["governed_action"])
        self.assertTrue(run["linked_incident_ids"])

    def test_unsupported_healthcare_output_is_blocked_before_action(self) -> None:
        run = self.pipelines.start(
            {
                "pipeline_id": "healthcare-visit-summary",
                "mode": "unsupported_output",
                "run_to_review": True,
            }
        )
        self.assertEqual(run["status"], "blocked")
        self.assertTrue(run["provider_invoked"])
        self.assertFalse(run["downstream_invoked"])
        self.assertIn("diagnosis_supported", run["validation"]["failure_codes"])
        self.assertIn("allergy_conflict_absent", run["validation"]["failure_codes"])
        self.assertIsNone(run["governed_action"])

    def test_unapproved_destination_blocks_before_provider_or_downstream(self) -> None:
        run = self.pipelines.start(
            {
                "pipeline_id": "healthcare-visit-summary",
                "mode": "unapproved_destination",
                "run_to_review": True,
            }
        )
        self.assertEqual(run["status"], "blocked")
        self.assertFalse(run["provider_invoked"])
        self.assertFalse(run["downstream_invoked"])
        self.assertEqual(
            run["validation"]["failure_codes"], ["unapproved_destination"]
        )
        self.assertTrue(run["linked_incident_ids"])

    def test_pipeline_and_governance_receipts_both_prevent_payload_mutation(self) -> None:
        run = self.pipelines.start(
            {"pipeline_id": "healthcare-visit-summary", "run_to_review": True}
        )
        self.pipelines.decide(
            run["run_id"],
            "attending-clinician-demo",
            True,
            "Clinician review completed.",
        )
        internal = self.pipelines.runs[run["run_id"]]
        internal.action_payload["summary"]["diagnosis"] = "Changed after approval"
        with self.assertRaises(PipelineWorkflowError):
            self.pipelines.execute(run["run_id"])

        other = self.pipelines.start(
            {"pipeline_id": "healthcare-visit-summary", "case_id": "HC-VISIT-319", "run_to_review": True}
        )
        approved = self.pipelines.decide(
            other["run_id"],
            "attending-clinician-demo",
            True,
            "Second fictional encounter reviewed.",
        )
        action_id = approved["governed_action"]["action"]["action_id"]
        self.application.service.get(action_id).request.parameters[
            "payload_sha256"
        ] = "tampered"
        with self.assertRaises(GovernanceWorkflowError):
            self.pipelines.execute(other["run_id"])

    def test_evidence_excludes_source_provider_model_and_tool_content(self) -> None:
        run = self.pipelines.start(
            {
                "pipeline_id": "healthcare-visit-summary",
                "mode": "unsupported_output",
                "run_to_review": True,
            }
        )
        evidence = self.pipelines.evidence(run["run_id"])
        serialized = json.dumps(evidence)
        self.assertEqual(evidence["schema"], "styrai.pipeline-evidence.v1")
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertIsNone(evidence["run"]["provider_payload"])
        self.assertIsNone(evidence["run"]["model_output"])
        self.assertIsNone(evidence["run"]["action_payload"])
        self.assertNotIn("MRN-DEMO-204", serialized)
        self.assertNotIn("Elin Sorensen", serialized)
        self.assertNotIn("Amoxicillin", serialized)


if __name__ == "__main__":
    unittest.main()
