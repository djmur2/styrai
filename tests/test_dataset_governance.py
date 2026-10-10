from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from murphyos.web import DemoApplication, StyrAIRequestHandler


POLICY_TEXT = (
    "Clause 4.2: Any AI-assisted credit recommendation with confidence below "
    "90% must receive manual review before action."
)


FINANCE_CSV = """record_id,domain,risk_class,ai_act_role,decision_mode,confidence,instructions_for_use_followed,human_oversight_available,oversight_person_competent,contains_personal_data,processing_purpose_documented,data_necessary,data_minimized,significant_effect,human_intervention_available,contestability_available,art22_exception_documented,manual_review_completed
FIN-001,financial_services,high_impact,deployer,advisory,0.83,true,true,true,true,true,true,true,true,true,true,true,false
FIN-002,financial_services,high_impact,deployer,advisory,0.96,true,true,true,true,true,true,true,true,true,true,true,false
"""


class DatasetGovernanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.application = DemoApplication(
            Path(self.temporary_directory.name) / "dataset-governance-audit.jsonl"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def draft_policy(self) -> dict[str, object]:
        return self.application.create_internal_policy_draft(
            {
                "name": "Synthetic Responsible Credit Policy",
                "filename": "responsible-credit-policy.txt",
                "text": POLICY_TEXT,
                "synthetic_policy_confirmed": True,
            }
        )

    def activate_policy(self) -> dict[str, object]:
        draft = self.draft_policy()
        return self.application.activate_internal_policy(
            draft["policy_id"],
            {
                "approved_by": "Synthetic Model Risk Committee",
                "rationale": "Approved for the local synthetic demonstration.",
                "approve_all_extracted_rules": True,
            },
        )

    def run_finance(self, policy_ids: list[str] | None = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": "Synthetic credit recommendations",
            "filename": "synthetic-finance.csv",
            "format": "csv",
            "content": FINANCE_CSV,
            "synthetic_data_confirmed": True,
        }
        if policy_ids is not None:
            payload["policy_ids"] = policy_ids
        return self.application.run_governance_dataset(payload)

    def test_regulation_library_is_versioned_and_cites_exact_official_sources(self) -> None:
        library = self.application.regulation_library()
        self.assertEqual(library["schema"], "styrai.regulation-library.v1")
        self.assertTrue(library["library_version"])
        self.assertGreaterEqual(len(library["sources"]), 4)
        required = {
            "source_id",
            "framework",
            "jurisdiction",
            "provision",
            "title",
            "requirement_summary",
            "official_url",
            "source_version",
            "application_or_review_date",
            "status",
        }
        for source in library["sources"]:
            self.assertTrue(required.issubset(source))
            self.assertTrue(source["official_url"].startswith("https://"))
        ai_act = next(
            source
            for source in library["sources"]
            if source["source_id"] == "EU-AIA-2024-1689-ART14"
        )
        self.assertEqual(ai_act["status"], "staged_readiness_mapping")
        self.assertIn("2027-12-02", ai_act["application_or_review_date"])

    def test_dataset_schema_exposes_executable_finance_and_healthcare_examples(self) -> None:
        schema = self.application.dataset_schema()
        self.assertEqual(schema["schema"], "styrai.synthetic-ai-outcomes.v1")
        self.assertIn("FIN-001", schema["examples"]["finance_csv"])
        self.assertEqual(schema["examples"]["healthcare_json"][0]["record_id"], "HC-001")
        self.assertIn("confidence below 90%", schema["policy_extractor_example"]["text"])
        record_id = next(item for item in schema["fields"] if item["name"] == "record_id")
        self.assertIn("case_id", record_id["aliases"])

    def test_written_policy_is_a_non_llm_draft_until_human_activation(self) -> None:
        draft = self.draft_policy()
        self.assertEqual(draft["status"], "draft")
        self.assertFalse(draft["extraction"]["llm_used"])
        self.assertEqual(draft["extraction"]["method"], "deterministic_pattern_matching")
        self.assertEqual(draft["extraction"]["rules_extracted"], 1)
        self.assertEqual(draft["rules"][0]["conditions"][0]["field"], "confidence")
        self.assertEqual(draft["rules"][0]["conditions"][0]["value"], 0.9)
        self.assertEqual(draft["rules"][0]["source_clause"], POLICY_TEXT)

        run = self.run_finance()
        self.assertEqual(run["summary"]["internal_policy_controls"]["tested"], 0)
        with self.assertRaisesRegex(ValueError, "activated"):
            self.run_finance([draft["policy_id"]])
        with self.assertRaisesRegex(ValueError, "approver"):
            self.application.activate_internal_policy(
                draft["policy_id"], {"approved_by": "", "rationale": ""}
            )

    def test_regulation_can_pass_while_stricter_company_policy_requires_review(self) -> None:
        policy = self.activate_policy()
        run = self.run_finance([policy["policy_id"]])

        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["dataset"]["records_evaluated"], 2)
        self.assertEqual(run["summary"]["overall_disposition"], "manual_review")
        self.assertEqual(run["summary"]["regulation_pass_internal_review"], 1)
        self.assertFalse(run["summary"]["percentage_score_used"])
        self.assertFalse(run["summary"]["legal_violation_confirmed"])

        counts = run["summary"]["regulatory_controls"]
        self.assertEqual(counts["total_checks"], 4)
        self.assertEqual(counts["tested"], 2)
        self.assertEqual(counts["applicable"], 2)
        self.assertEqual(counts["passed"], 2)
        self.assertEqual(counts["failed"], 0)
        self.assertEqual(counts["not_applicable"], 2)
        readiness = run["summary"]["future_readiness_controls"]
        self.assertEqual(readiness["ready"], 2)

        first = run["row_results"][0]
        self.assertEqual(first["regulatory_outcome"], "pass")
        self.assertEqual(first["internal_policy_outcome"], "manual_review")
        self.assertEqual(first["disposition"], "manual_review")
        policy_finding = next(
            item
            for item in first["findings"]
            if item["source_authority"] == "internal_policy"
        )
        self.assertEqual(policy_finding["citation"]["provision"], "COMPANY-4.2")
        self.assertEqual(policy_finding["citation"]["source_clause"], POLICY_TEXT)

        second = run["row_results"][1]
        self.assertEqual(second["disposition"], "pass")
        self.assertEqual(second["internal_policy_outcome"], "pass")

    def test_json_run_returns_row_level_regulatory_gap_and_exact_provision(self) -> None:
        run = self.application.run_governance_dataset(
            {
                "name": "Synthetic clinical output review",
                "filename": "synthetic-healthcare.json",
                "format": "json",
                "synthetic_data_confirmed": True,
                "content": json.dumps(
                    [
                        {
                            "record_id": "HC-001",
                            "domain": "healthcare",
                            "risk_class": "high_impact",
                            "decision_mode": "advisory",
                            "ai_act_role": "deployer",
                            "instructions_for_use_followed": True,
                            "human_oversight_available": True,
                            "oversight_person_competent": True,
                            "contains_personal_data": True,
                            "processing_purpose_documented": True,
                            "data_necessary": False,
                            "data_minimized": True,
                        }
                    ]
                ),
            }
        )
        self.assertEqual(run["summary"]["overall_disposition"], "action_required")
        row = run["row_results"][0]
        self.assertEqual(row["regulatory_outcome"], "potential_control_gap")
        transparency = next(
            item for item in row["control_results"] if item["control_id"] == "REG-DAT-001"
        )
        self.assertEqual(transparency["status"], "fail")
        self.assertEqual(transparency["source"]["provision"], "Article 5(1)(c)")
        self.assertFalse(transparency["legal_violation_confirmed"])
        self.assertIn("eur-lex", transparency["source"]["official_url"])

    def test_missing_applicable_evidence_is_not_counted_as_pass(self) -> None:
        run = self.application.run_governance_dataset(
            {
                "name": "Incomplete synthetic record",
                "records": [
                    {
                        "record_id": "MISSING-001",
                        "risk_class": "high_impact",
                        "human_oversight_available": True,
                    }
                ],
                "synthetic_data_confirmed": True,
            }
        )
        counts = run["summary"]["future_readiness_controls"]
        self.assertEqual(counts["insufficient_evidence"], 1)
        self.assertEqual(run["summary"]["overall_disposition"], "insufficient_evidence")
        self.assertEqual(run["summary"]["records_passed"], 0)

    def test_case_id_and_human_review_aliases_are_supported(self) -> None:
        policy = self.activate_policy()
        run = self.application.run_governance_dataset(
            {
                "name": "Legacy-shaped synthetic row",
                "records": [
                    {
                        "case_id": "ALIAS-001",
                        "domain": "financial_services",
                        "risk_class": "high_impact",
                        "decision_mode": "advisory",
                        "confidence": 0.81,
                        "human_oversight_available": True,
                        "explanation_present": True,
                        "contains_personal_data": False,
                        "human_review": False,
                    }
                ],
                "policy_ids": [policy["policy_id"]],
                "synthetic_data_confirmed": True,
            }
        )
        self.assertEqual(run["row_results"][0]["record_id"], "ALIAS-001")
        self.assertEqual(run["row_results"][0]["disposition"], "manual_review")

    def test_run_evidence_preserves_dataset_hash_rule_versions_and_audit_chain(self) -> None:
        policy = self.activate_policy()
        run = self.run_finance([policy["policy_id"]])
        evidence = self.application.ai_governance_evidence(run["run_id"])
        self.assertEqual(evidence["schema"], "styrai.dataset-governance-evidence.v1")
        self.assertTrue(evidence["audit_chain_valid"])
        self.assertEqual(
            evidence["subject"]["dataset"]["sha256"], run["dataset"]["sha256"]
        )
        self.assertEqual(
            evidence["subject"]["rule_set"]["regulation_library_version"],
            evidence["regulation_library"]["library_version"],
        )
        self.assertEqual(
            evidence["subject"]["rule_set"]["internal_policies"][0]["version"],
            "1.0",
        )

    def test_real_or_unconfirmed_material_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "synthetic"):
            self.application.create_internal_policy_draft(
                {"name": "Policy", "text": POLICY_TEXT}
            )
        with self.assertRaisesRegex(ValueError, "synthetic"):
            self.application.run_governance_dataset(
                {"records": [{"record_id": "X"}]}
            )

    def test_all_not_applicable_rules_are_not_reported_as_a_pass(self) -> None:
        run = self.application.run_governance_dataset(
            {
                "name": "Unscoped synthetic record",
                "records": [{"record_id": "NA-001", "domain": "other"}],
                "synthetic_data_confirmed": True,
            }
        )
        self.assertEqual(run["row_results"][0]["regulatory_outcome"], "not_assessed")
        self.assertEqual(run["row_results"][0]["disposition"], "not_assessed")
        self.assertEqual(run["summary"]["overall_disposition"], "not_assessed")
        self.assertEqual(run["summary"]["records_passed"], 0)

    def test_duplicate_ids_and_non_finite_confidence_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.application.run_governance_dataset(
                {
                    "records": [{"record_id": "DUP"}, {"record_id": "DUP"}],
                    "synthetic_data_confirmed": True,
                }
            )
        with self.assertRaisesRegex(ValueError, "non-finite"):
            self.application.run_governance_dataset(
                {
                    "records": [{"record_id": "NAN", "confidence": "NaN"}],
                    "synthetic_data_confirmed": True,
                }
            )

    def test_negated_review_clause_is_retained_but_not_turned_into_a_rule(self) -> None:
        draft = self.application.create_internal_policy_draft(
            {
                "name": "Negated synthetic policy",
                "text": (
                    "Clause 8: AI-assisted credit recommendations below 90% do not "
                    "require manual review."
                ),
                "synthetic_policy_confirmed": True,
            }
        )
        self.assertEqual(draft["extraction"]["rules_extracted"], 0)
        self.assertTrue(draft["unparsed_clauses"])
        with self.assertRaisesRegex(ValueError, "No enforceable"):
            self.application.activate_internal_policy(
                draft["policy_id"],
                {
                    "approved_by": "Reviewer",
                    "rationale": "Synthetic test",
                    "approve_all_extracted_rules": True,
                },
            )

    def test_model_statistics_use_uploaded_rows_and_expose_denominators(self) -> None:
        run = self.application.run_governance_dataset(
            {
                "name": "Synthetic metrics",
                "synthetic_data_confirmed": True,
                "records": [
                    {
                        "record_id": "BASE-1",
                        "confidence": 0.8,
                        "predicted_label": "approve",
                        "actual_label": "approve",
                        "protected_group": "A",
                        "adverse_action": False,
                        "population": "baseline",
                        "score": 0.2,
                    },
                    {
                        "record_id": "BASE-2",
                        "confidence": 0.6,
                        "predicted_label": "approve",
                        "actual_label": "deny",
                        "protected_group": "B",
                        "adverse_action": True,
                        "population": "baseline",
                        "score": 0.4,
                    },
                    {
                        "record_id": "CURR-1",
                        "confidence": 1.0,
                        "protected_group": "A",
                        "adverse_action": True,
                        "population": "current",
                        "score": 0.8,
                    },
                ],
            }
        )
        statistics = run["model_statistics"]
        self.assertEqual(statistics["confidence"]["denominator"], 3)
        self.assertAlmostEqual(statistics["confidence"]["mean"], 0.8)
        self.assertEqual(statistics["observed_error_rate"]["denominator"], 2)
        self.assertEqual(statistics["observed_error_rate"]["errors"], 1)
        self.assertAlmostEqual(statistics["observed_error_rate"]["value"], 0.5)
        self.assertEqual(
            statistics["group_adverse_action_rates"]["eligible_records"], 3
        )
        self.assertEqual(
            statistics["population_stability_index"]["status"], "calculated"
        )


class MultipartParsingTests(unittest.TestCase):
    def test_standard_library_parser_reads_one_utf8_csv_upload(self) -> None:
        boundary = "----StyrAITestBoundary"
        parts = [
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="name"\r\n\r\n'
                "Synthetic upload\r\n"
            ),
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="synthetic_data_confirmed"\r\n\r\n'
                "true\r\n"
            ),
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="sample.csv"\r\n'
                "Content-Type: text/csv; charset=utf-8\r\n\r\n"
                "record_id,confidence\r\nROW-1,0.82\r\n"
            ),
            f"--{boundary}--\r\n",
        ]
        body = "".join(parts).encode("utf-8")

        class ParsingHandler(StyrAIRequestHandler):
            def __init__(self) -> None:
                self.path = "/api/governance/dataset-runs"
                self.headers = {
                    "Content-Length": str(len(body)),
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                }
                self.rfile = io.BytesIO(body)

        payload = ParsingHandler()._read_json()
        self.assertEqual(payload["filename"], "sample.csv")
        self.assertEqual(payload["name"], "Synthetic upload")
        self.assertEqual(payload["synthetic_data_confirmed"], "true")
        self.assertIn("ROW-1,0.82", payload["content"])


class DatasetGovernanceHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.application = DemoApplication(
            Path(self.temporary_directory.name) / "dataset-http-audit.jsonl"
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

    def test_library_schema_and_dataset_run_routes(self) -> None:
        regulation_handler = self.handler("/api/governance/regulations")
        regulation_handler.do_GET()
        self.assertEqual(regulation_handler.sent["schema"], "styrai.regulation-library.v1")

        schema_handler = self.handler("/api/governance/dataset-schema")
        schema_handler.do_GET()
        self.assertIn("finance_csv", schema_handler.sent["examples"])

        run_handler = self.handler(
            "/api/governance/dataset-runs",
            {
                "name": "HTTP synthetic run",
                "records": [{"record_id": "HTTP-1"}],
                "synthetic_data_confirmed": True,
            },
        )
        run_handler.do_POST()
        self.assertEqual(int(run_handler.status), 201)
        self.assertEqual(run_handler.sent["dataset"]["records_evaluated"], 1)

        read_handler = self.handler(
            f"/api/governance/dataset-runs/{run_handler.sent['run_id']}"
        )
        read_handler.do_GET()
        self.assertEqual(read_handler.sent["run_id"], run_handler.sent["run_id"])


if __name__ == "__main__":
    unittest.main()
