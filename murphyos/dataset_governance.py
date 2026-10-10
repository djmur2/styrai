"""Deterministic dataset and written-policy governance for the local demo.

This module deliberately does not call an LLM.  It turns a small, documented
synthetic-data schema into reproducible control results and extracts only a
conservative set of machine-readable rules from written company policy.  A
human must activate an extracted draft before it can affect a run.

The regulatory rules below are demonstrative control proxies.  A failed rule
is reported as a potential control gap requiring qualified review, never as a
legal conclusion.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .audit import AuditIntegrityError, HashChainedAuditLog


REGULATION_LIBRARY_VERSION = "2026.10-demo.2"
DATASET_SCHEMA_VERSION = "styrai.synthetic-ai-outcomes.v1"
RULE_ENGINE_VERSION = "styrai.deterministic-controls.v2"
MAX_DATASET_CHARACTERS = 512_000
MAX_POLICY_CHARACTERS = 20_000
MAX_RECORDS = 500
MAX_COLUMNS = 100
MAX_CELL_CHARACTERS = 2_000


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


REGULATION_LIBRARY: tuple[dict[str, Any], ...] = (
    {
        "source_id": "EU-AIA-2024-1689-ART14",
        "framework": "EU AI Act",
        "jurisdiction": "European Union",
        "provision": "Article 14",
        "title": "Human oversight",
        "requirement_summary": (
            "High-risk AI systems must be designed and developed so that they can "
            "be effectively overseen by natural persons during use."
        ),
        "official_url": "https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-14",
        "source_version": (
            "Regulation (EU) 2024/1689; staged implementation context reviewed "
            "2026-10-10"
        ),
        "application_or_review_date": (
            "Readiness mapping for Annex III high-risk obligations: 2027-12-02; "
            "actual applicability depends on legal classification"
        ),
        "status": "staged_readiness_mapping",
        "control_id": "REF-PROVIDER-HUM-001",
        "evaluation_scope": "library_reference_only",
        "control_proxy": (
            "When a record is marked high-risk, evidence must show that a human-"
            "oversight mechanism is available."
        ),
    },
    {
        "source_id": "EU-AIA-2024-1689-ART13",
        "framework": "EU AI Act",
        "jurisdiction": "European Union",
        "provision": "Article 13",
        "title": "Transparency and provision of information to deployers",
        "requirement_summary": (
            "High-risk AI systems must be sufficiently transparent to enable "
            "deployers to interpret output and use it appropriately."
        ),
        "official_url": "https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-13",
        "source_version": (
            "Regulation (EU) 2024/1689; staged implementation context reviewed "
            "2026-10-10"
        ),
        "application_or_review_date": (
            "Readiness mapping for Annex III high-risk obligations: 2027-12-02; "
            "actual applicability depends on legal classification"
        ),
        "status": "staged_readiness_mapping",
        "control_id": "REF-PROVIDER-TRA-001",
        "evaluation_scope": "library_reference_only",
        "control_proxy": "Library reference only; no per-row legal test is inferred.",
    },
    {
        "source_id": "EU-AIA-2024-1689-ART26-1-2",
        "framework": "EU AI Act",
        "jurisdiction": "European Union",
        "provision": "Article 26(1)-(2)",
        "title": "Obligations of deployers of high-risk AI systems",
        "requirement_summary": (
            "Deployers must take appropriate technical and organisational measures "
            "to use high-risk systems in accordance with instructions and assign "
            "human oversight to competent natural persons."
        ),
        "official_url": "https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-26",
        "source_version": (
            "Regulation (EU) 2024/1689; staged implementation context reviewed "
            "2026-10-10"
        ),
        "application_or_review_date": (
            "Readiness mapping for Annex III high-risk obligations: 2027-12-02; "
            "actual applicability depends on role and legal classification"
        ),
        "status": "staged_readiness_mapping",
        "control_id": "READY-DEP-001",
        "evaluation_scope": "future_readiness",
        "control_proxy": (
            "For a self-identified high-risk candidate where the organisation acts "
            "as deployer, capture evidence of instructions-following and competent "
            "human oversight."
        ),
    },
    {
        "source_id": "GDPR-2016-679-ART5-1-C",
        "framework": "GDPR",
        "jurisdiction": "European Union / EEA",
        "provision": "Article 5(1)(c)",
        "title": "Data minimisation",
        "requirement_summary": (
            "Personal data must be adequate, relevant and limited to what is "
            "necessary in relation to the purposes for which it is processed."
        ),
        "official_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        "source_version": "Regulation (EU) 2016/679",
        "application_or_review_date": "Applicable since 2018-05-25",
        "status": "in_force",
        "control_id": "REG-DAT-001",
        "evaluation_scope": "current_law_control_proxy",
        "control_proxy": (
            "When a record is marked as containing personal data, evidence must "
            "show that the input was minimised."
        ),
    },
    {
        "source_id": "GDPR-2016-679-ART22",
        "framework": "GDPR",
        "jurisdiction": "European Union / EEA",
        "provision": "Article 22",
        "title": "Automated individual decision-making",
        "requirement_summary": (
            "A data subject has protections concerning a decision based solely on "
            "automated processing that produces legal or similarly significant "
            "effects, subject to the provision's conditions and safeguards."
        ),
        "official_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
        "source_version": "Regulation (EU) 2016/679",
        "application_or_review_date": "Applicable since 2018-05-25",
        "status": "in_force",
        "control_id": "REG-AUT-001",
        "evaluation_scope": "current_law_control_proxy",
        "control_proxy": (
            "A solely automated, significant decision must carry evidence of human "
            "intervention and contestability safeguards."
        ),
    },
)


def public_regulation_library() -> dict[str, Any]:
    """Return a JSON-ready, versioned snapshot of the housed sources."""

    return {
        "schema": "styrai.regulation-library.v1",
        "library_version": REGULATION_LIBRARY_VERSION,
        "reviewed_at": "2026-10-10",
        "sources": [dict(item) for item in REGULATION_LIBRARY],
        "interpretation_notice": (
            "These are deterministic demonstration controls and readiness mappings. "
            "A result is not a legal opinion or a confirmed legal violation."
        ),
    }


def public_dataset_schema() -> dict[str, Any]:
    """Describe the small upload contract and provide executable examples."""

    finance_csv = (
        "record_id,domain,risk_class,ai_act_role,decision_mode,confidence,"
        "instructions_for_use_followed,human_oversight_available,"
        "oversight_person_competent,contains_personal_data,"
        "processing_purpose_documented,data_necessary,data_minimized,"
        "significant_effect,human_intervention_available,"
        "contestability_available,art22_exception_documented,"
        "manual_review_completed\n"
        "FIN-001,financial_services,high_impact,deployer,advisory,0.83,true,"
        "true,true,true,true,true,true,true,true,true,true,false\n"
        "FIN-002,financial_services,high_impact,deployer,advisory,0.96,true,"
        "true,true,true,true,true,true,true,true,true,true,false\n"
    )
    healthcare_json = [
        {
            "record_id": "HC-001",
            "domain": "healthcare",
            "risk_class": "high_impact",
            "ai_act_role": "deployer",
            "decision_mode": "advisory",
            "confidence": 0.88,
            "instructions_for_use_followed": True,
            "human_oversight_available": True,
            "oversight_person_competent": True,
            "contains_personal_data": True,
            "processing_purpose_documented": True,
            "data_necessary": True,
            "data_minimized": True,
            "manual_review_completed": True,
        },
        {
            "record_id": "HC-002",
            "domain": "healthcare",
            "risk_class": "high_impact",
            "ai_act_role": "deployer",
            "decision_mode": "advisory",
            "confidence": 0.97,
            "instructions_for_use_followed": True,
            "human_oversight_available": True,
            "oversight_person_competent": True,
            "contains_personal_data": True,
            "processing_purpose_documented": True,
            "data_necessary": True,
            "data_minimized": True,
            "manual_review_completed": True,
        },
    ]
    return {
        "schema": DATASET_SCHEMA_VERSION,
        "formats": ["csv", "json"],
        "limits": {
            "records": MAX_RECORDS,
            "columns": MAX_COLUMNS,
            "characters": MAX_DATASET_CHARACTERS,
            "cell_characters": MAX_CELL_CHARACTERS,
        },
        "fields": [
            {
                "name": "record_id",
                "aliases": ["case_id"],
                "type": "string",
                "required": True,
                "meaning": "Stable synthetic row identifier.",
            },
            {
                "name": "domain",
                "type": "string",
                "required": False,
                "examples": ["financial_services", "healthcare"],
                "meaning": "Business domain used by internal-policy applicability rules.",
            },
            {
                "name": "risk_class",
                "type": "string",
                "required": False,
                "examples": ["high_impact", "limited"],
                "meaning": "Demo classification input; it is not a legal classification.",
            },
            {
                "name": "decision_mode",
                "type": "string",
                "required": False,
                "examples": ["advisory", "ai_assisted", "solely_automated"],
                "meaning": "How the model output participates in the decision.",
            },
            {
                "name": "ai_act_role",
                "type": "string",
                "required": False,
                "examples": ["deployer", "provider"],
                "meaning": (
                    "Self-declared role used only to select a readiness mapping; it "
                    "does not determine legal applicability."
                ),
            },
            {
                "name": "confidence",
                "type": "number between 0 and 1",
                "required": False,
                "meaning": "Model confidence used by an extracted threshold policy.",
            },
            {
                "name": "human_oversight_available",
                "type": "boolean",
                "required": False,
                "meaning": (
                    "Whether an oversight mechanism exists; distinct from whether this "
                    "specific row completed manual review."
                ),
            },
            {
                "name": "manual_review_completed",
                "aliases": ["human_review"],
                "type": "boolean",
                "required": False,
                "meaning": "Whether this individual record completed company-required review.",
            },
            {
                "name": "instructions_for_use_followed",
                "type": "boolean",
                "required": False,
                "meaning": "Readiness evidence for the deployer obligation mapping.",
            },
            {
                "name": "oversight_person_competent",
                "type": "boolean",
                "required": False,
                "meaning": "Readiness evidence that assigned oversight is competent.",
            },
            {
                "name": "contains_personal_data",
                "type": "boolean",
                "required": False,
                "meaning": "Activates the GDPR data-minimisation proxy when true.",
            },
            {
                "name": "data_minimized",
                "type": "boolean",
                "required": False,
                "meaning": "Evidence input for the GDPR Article 5(1)(c) proxy.",
            },
            {
                "name": "processing_purpose_documented",
                "type": "boolean",
                "required": False,
                "meaning": "Supporting purpose evidence for the data-minimisation proxy.",
            },
            {
                "name": "data_necessary",
                "type": "boolean",
                "required": False,
                "meaning": "Supporting necessity evidence for the data-minimisation proxy.",
            },
            {
                "name": "significant_effect",
                "type": "boolean",
                "required": False,
                "meaning": "Along with solely_automated mode, activates the Article 22 proxy.",
            },
            {
                "name": "human_intervention_available",
                "type": "boolean",
                "required": False,
                "meaning": "Safeguard evidence for the Article 22 proxy.",
            },
            {
                "name": "contestability_available",
                "type": "boolean",
                "required": False,
                "meaning": "Safeguard evidence for the Article 22 proxy.",
            },
            {
                "name": "art22_exception_documented",
                "type": "boolean",
                "required": False,
                "meaning": (
                    "Whether a documented Article 22(2) condition is recorded; the "
                    "prototype does not decide whether that basis is legally sufficient."
                ),
            },
            {
                "name": "predicted_label",
                "type": "string",
                "required": False,
                "meaning": "Compared with actual_label to calculate an observed error rate.",
            },
            {
                "name": "actual_label",
                "type": "string",
                "required": False,
                "meaning": "Ground truth used as the error-rate denominator when present.",
            },
            {
                "name": "population",
                "type": "string",
                "required": False,
                "examples": ["baseline", "current"],
                "meaning": "Population label used with score to calculate PSI.",
            },
            {
                "name": "score",
                "type": "number between 0 and 1",
                "required": False,
                "meaning": "Model score used for fixed-bin PSI when both populations exist.",
            },
            {
                "name": "protected_group",
                "type": "string",
                "required": False,
                "meaning": "Accepted metadata for future group analysis; not scored in v1.",
            },
            {
                "name": "adverse_action",
                "type": "boolean",
                "required": False,
                "meaning": "Accepted outcome metadata for future group analysis; not scored in v1.",
            },
        ],
        "policy_extractor_example": {
            "text": (
                "Clause 4.2: Any AI-assisted credit recommendation with confidence "
                "below 90% must receive manual review before action."
            ),
            "effect": (
                "After explicit activation, finance rows below 0.90 require manual "
                "review even when every applicable regulatory proxy passes."
            ),
            "llm_required": False,
        },
        "examples": {
            "finance_csv": finance_csv,
            "healthcare_json": healthcare_json,
        },
        "statistics_notice": (
            "Runs report discrete record-by-control counts. They do not produce a "
            "legal compliance percentage."
        ),
    }


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1"}:
            return True
        if normalized in {"false", "no", "n", "0"}:
            return False
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return None


def _coerce_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return None
    if isinstance(value, str) and value.strip().endswith("%"):
        number /= 100
    return number if math.isfinite(number) else None


def _normalized_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key).strip().lower(): value for key, value in row.items()}


def _status_counts(results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = {
        "passed": 0,
        "failed": 0,
        "manual_review": 0,
        "insufficient_evidence": 0,
        "not_applicable": 0,
    }
    for result in results:
        status = str(result["status"])
        key = {
            "pass": "passed",
            "fail": "failed",
            "manual_review": "manual_review",
            "insufficient_evidence": "insufficient_evidence",
            "not_applicable": "not_applicable",
        }[status]
        statuses[key] += 1
    total_checks = len(results)
    not_applicable = statuses["not_applicable"]
    return {
        "total_checks": total_checks,
        "tested": total_checks - not_applicable,
        "applicable": total_checks - not_applicable,
        **statuses,
        "definition": (
            "Total checks includes not-applicable rules. Tested/applicable excludes "
            "not-applicable rules; passed is never inferred from missing evidence."
        ),
    }


def _readiness_counts(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_checks = len(results)
    not_applicable = sum(item["status"] == "not_applicable" for item in results)
    return {
        "total_checks": total_checks,
        "tested": total_checks - not_applicable,
        "applicable": total_checks - not_applicable,
        "ready": sum(item["status"] == "future_readiness" for item in results),
        "readiness_gaps": sum(item["status"] == "readiness_gap" for item in results),
        "insufficient_evidence": sum(
            item["status"] == "insufficient_evidence" for item in results
        ),
        "not_applicable": not_applicable,
        "definition": (
            "Readiness results are forward-looking operational checks. They are "
            "excluded from current-law pass/fail counts and do not establish legal "
            "classification or applicability."
        ),
    }


class DatasetGovernanceEngine:
    """In-memory synthetic dataset runner and internal-policy registry."""

    def __init__(self, audit_log: HashChainedAuditLog) -> None:
        self.audit_log = audit_log
        self.policies: dict[str, dict[str, Any]] = {}
        self.runs: dict[str, dict[str, Any]] = {}

    def regulations(self) -> dict[str, Any]:
        return public_regulation_library()

    def dataset_schema(self) -> dict[str, Any]:
        return public_dataset_schema()

    @staticmethod
    def _require_synthetic(payload: dict[str, Any], field: str) -> None:
        if _coerce_bool(payload.get(field)) is not True:
            raise ValueError(
                "This demonstration environment accepts synthetic material only; "
                f"set {field}=true to confirm."
            )

    @staticmethod
    def _policy_clauses(text: str) -> list[str]:
        parts = re.split(
            r"(?:\r?\n+|;+\s*|(?<=[.!?])\s+(?=[A-Z]))",
            text,
        )
        return [" ".join(item.split()) for item in parts if item.strip()]

    @staticmethod
    def _clause_id(clause: str, index: int) -> str:
        match = re.search(r"(?i)\b(?:clause|section|policy)\s+([A-Z0-9.-]+)", clause)
        return (
            f"COMPANY-{match.group(1).upper()}"
            if match
            else f"COMPANY-CLAUSE-{index:03d}"
        )

    def _extract_policy_rules(
        self, text: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        rules: list[dict[str, Any]] = []
        clauses: list[dict[str, Any]] = []
        unparsed: list[str] = []
        for index, clause in enumerate(self._policy_clauses(text), start=1):
            clause_id = self._clause_id(clause, index)
            clause_rules: list[str] = []
            lower = clause.lower()
            manual_language = any(
                phrase in lower
                for phrase in (
                    "manual review",
                    "human review",
                    "reviewed by a human",
                    "human approval",
                )
            )
            negated_manual_language = bool(
                re.search(
                    r"(?i)\b(?:does\s+not|do\s+not|need\s+not|not\s+required\s+to|"
                    r"without)\b.{0,35}\b(?:manual|human)\s+(?:review|approval)\b",
                    clause,
                )
                or re.search(
                    r"(?i)\b(?:no\s+(?:manual|human)\s+(?:review|approval)|"
                    r"(?:manual|human)\s+(?:review|approval)\s+is\s+not\s+required)\b",
                    clause,
                )
            )
            if negated_manual_language:
                manual_language = False
            confidence = re.search(
                r"(?i)\bconfidence(?:\s+score)?(?:\s+is)?\s*"
                r"(below|under|less\s+than|<|at\s+most|<=)\s*"
                r"(\d+(?:\.\d+)?)\s*(%)?",
                clause,
            )
            if manual_language and confidence:
                raw_threshold = float(confidence.group(2))
                threshold = raw_threshold / 100 if confidence.group(3) else raw_threshold
                if not 0 <= threshold <= 1:
                    unparsed.append(clause)
                else:
                    conditions: list[dict[str, Any]] = [
                        {"field": "confidence", "operator": "less_than", "value": threshold}
                    ]
                    if "credit" in lower or "loan" in lower:
                        conditions.append(
                            {
                                "field": "domain",
                                "operator": "in",
                                "value": ["finance", "financial_services", "credit"],
                            }
                        )
                    elif any(word in lower for word in ("clinical", "patient", "health")):
                        conditions.append(
                            {
                                "field": "domain",
                                "operator": "in",
                                "value": ["healthcare", "clinical"],
                            }
                        )
                    rule_id = f"{clause_id}-R{len(rules) + 1:02d}"
                    rules.append(
                        {
                            "rule_id": rule_id,
                            "rule_version": "1.0-draft",
                            "source_authority": "internal_policy",
                            "clause_id": clause_id,
                            "source_clause": clause,
                            "source_clause_sha256": hashlib.sha256(
                                clause.encode("utf-8")
                            ).hexdigest(),
                            "source_locator": {
                                "clause_index": index,
                                "character_start": max(text.find(clause), 0),
                                "character_end": max(text.find(clause), 0) + len(clause),
                            },
                            "activation_status": "draft",
                            "conditions": conditions,
                            "requirement": {
                                "action": "manual_review",
                                "evidence_field": "manual_review_completed",
                            },
                            "description": (
                                f"Require manual review when model confidence is below "
                                f"{threshold:.0%}."
                            ),
                        }
                    )
                    clause_rules.append(rule_id)
            elif manual_language and any(
                phrase in lower
                for phrase in ("ai-assisted", "ai assisted", "automated decision")
            ):
                conditions = [
                    {
                        "field": "decision_mode",
                        "operator": "in",
                        "value": ["advisory", "ai_assisted", "automated", "solely_automated"],
                    }
                ]
                if "credit" in lower or "loan" in lower:
                    conditions.append(
                        {
                            "field": "domain",
                            "operator": "in",
                            "value": ["finance", "financial_services", "credit"],
                        }
                    )
                elif any(word in lower for word in ("clinical", "patient", "health")):
                    conditions.append(
                        {
                            "field": "domain",
                            "operator": "in",
                            "value": ["healthcare", "clinical"],
                        }
                    )
                rule_id = f"{clause_id}-R{len(rules) + 1:02d}"
                rules.append(
                    {
                        "rule_id": rule_id,
                        "rule_version": "1.0-draft",
                        "source_authority": "internal_policy",
                        "clause_id": clause_id,
                        "source_clause": clause,
                        "source_clause_sha256": hashlib.sha256(
                            clause.encode("utf-8")
                        ).hexdigest(),
                        "source_locator": {
                            "clause_index": index,
                            "character_start": max(text.find(clause), 0),
                            "character_end": max(text.find(clause), 0) + len(clause),
                        },
                        "activation_status": "draft",
                        "conditions": conditions,
                        "requirement": {
                            "action": "manual_review",
                            "evidence_field": "manual_review_completed",
                        },
                        "description": "Require human review for the described AI-assisted use.",
                    }
                )
                clause_rules.append(rule_id)
            else:
                unparsed.append(clause)
            clauses.append(
                {
                    "clause_id": clause_id,
                    "text": clause,
                    "parsed": bool(clause_rules),
                    "rule_ids": clause_rules,
                }
            )
        return rules, clauses, unparsed

    def create_policy_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_synthetic(payload, "synthetic_policy_confirmed")
        name = str(payload.get("name", "")).strip()
        text = str(payload.get("text", payload.get("content", ""))).strip()
        filename = Path(str(payload.get("filename", "written-policy.txt"))).name
        if not name:
            raise ValueError("A policy name is required.")
        if not text:
            raise ValueError("Written policy text is required.")
        if len(text) > MAX_POLICY_CHARACTERS:
            raise ValueError("Written policy exceeds the 20,000 character demo limit.")
        rules, clauses, unparsed = self._extract_policy_rules(text)
        policy_id = _identifier("POL")
        created_at = _now()
        policy = {
            "schema": "styrai.internal-policy.v1",
            "policy_id": policy_id,
            "name": name[:160],
            "filename": filename[:160],
            "status": "draft",
            "version": "1.0-draft",
            "created_at": created_at,
            "activated_at": None,
            "approved_by": None,
            "approval_rationale": None,
            "active_rule_ids": [],
            "synthetic": True,
            "source_text": text,
            "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "extraction": {
                "method": "deterministic_pattern_matching",
                "engine_version": RULE_ENGINE_VERSION,
                "llm_used": False,
                "rules_extracted": len(rules),
                "human_activation_required": True,
            },
            "clauses": clauses,
            "rules": rules,
            "unparsed_clauses": unparsed,
            "warnings": [
                "Only recognised, deterministic patterns were drafted.",
                "Unparsed clauses are retained for human review and are not enforced.",
            ],
        }
        self.policies[policy_id] = policy
        self.audit_log.append(
            "governance.policy_draft_created",
            policy_id,
            {
                "policy_id": policy_id,
                "name": policy["name"],
                "source_sha256": policy["source_sha256"],
                "rules": rules,
                "status": "draft",
                "synthetic": True,
            },
        )
        return policy

    def activate_policy(self, policy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        policy = self.policies.get(policy_id)
        if policy is None:
            raise ValueError("Unknown internal policy.")
        if policy["status"] == "active":
            return policy
        if not policy["rules"]:
            raise ValueError(
                "No enforceable deterministic rules were extracted; review and revise "
                "the written policy before activation."
            )
        approved_by = str(payload.get("approved_by", "")).strip()
        rationale = str(payload.get("rationale", "")).strip()
        if not approved_by or not rationale:
            raise ValueError("An approver and activation rationale are required.")
        requested_rule_ids = payload.get("approved_rule_ids")
        if requested_rule_ids is None and _coerce_bool(
            payload.get("approve_all_extracted_rules")
        ) is True:
            requested_rule_ids = [item["rule_id"] for item in policy["rules"]]
        if not isinstance(requested_rule_ids, list) or not requested_rule_ids:
            raise ValueError(
                "Explicitly supply approved_rule_ids, or set "
                "approve_all_extracted_rules=true after reviewing every extracted clause."
            )
        known_rule_ids = {item["rule_id"] for item in policy["rules"]}
        approved_rule_ids = {str(item) for item in requested_rule_ids}
        unknown_rule_ids = approved_rule_ids - known_rule_ids
        if unknown_rule_ids:
            raise ValueError(
                f"Unknown extracted rule identifiers: {', '.join(sorted(unknown_rule_ids))}."
            )
        policy["status"] = "active"
        policy["version"] = "1.0"
        policy["activated_at"] = _now()
        policy["approved_by"] = approved_by[:160]
        policy["approval_rationale"] = rationale[:500]
        policy["active_rule_ids"] = sorted(approved_rule_ids)
        for rule in policy["rules"]:
            rule["rule_version"] = "1.0"
            rule["activation_status"] = (
                "active" if rule["rule_id"] in approved_rule_ids else "not_approved"
            )
        self.audit_log.append(
            "governance.policy_activated",
            policy_id,
            {
                "policy_id": policy_id,
                "version": policy["version"],
                "source_sha256": policy["source_sha256"],
                "approved_by": policy["approved_by"],
                "rationale": policy["approval_rationale"],
                "rule_ids": policy["active_rule_ids"],
            },
        )
        return policy

    def list_policies(self) -> list[dict[str, Any]]:
        return list(reversed(list(self.policies.values())))

    @staticmethod
    def _parse_dataset(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str, str]:
        raw_records = payload.get("records")
        filename = Path(str(payload.get("filename", "synthetic-dataset.csv"))).name
        requested_format = str(payload.get("format", "")).strip().lower()
        if isinstance(raw_records, list):
            records = raw_records
            raw_for_hash = json.dumps(
                raw_records, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            )
            dataset_format = "json"
        else:
            content = payload.get("content", "")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("CSV/JSON dataset content or a records array is required.")
            if len(content) > MAX_DATASET_CHARACTERS:
                raise ValueError("Dataset exceeds the 512,000 character demo limit.")
            raw_for_hash = content
            if requested_format in {"csv", "json"}:
                dataset_format = requested_format
            elif filename.lower().endswith(".json") or content.lstrip().startswith(("[", "{")):
                dataset_format = "json"
            else:
                dataset_format = "csv"
            if dataset_format == "csv":
                reader = csv.DictReader(io.StringIO(content))
                if not reader.fieldnames:
                    raise ValueError("CSV dataset requires a header row.")
                if len(reader.fieldnames) > MAX_COLUMNS:
                    raise ValueError("Dataset exceeds the 100 column demo limit.")
                normalized_headers = [str(item).strip().lower() for item in reader.fieldnames]
                if any(not item for item in normalized_headers):
                    raise ValueError("CSV dataset contains an empty column name.")
                if len(set(normalized_headers)) != len(normalized_headers):
                    raise ValueError("CSV dataset column names must be unique.")
                records = list(reader)
            else:
                decoded = json.loads(content)
                if isinstance(decoded, dict):
                    decoded = decoded.get("records")
                if not isinstance(decoded, list):
                    raise ValueError("JSON dataset must be an array or an object with records.")
                records = decoded
        if not records:
            raise ValueError("Dataset must contain at least one record.")
        if len(records) > MAX_RECORDS:
            raise ValueError("Dataset exceeds the 500 record demo limit.")
        clean_records: list[dict[str, Any]] = []
        seen_record_ids: set[str] = set()
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise ValueError(f"Dataset record {index} must be an object or CSV row.")
            if len(record) > MAX_COLUMNS:
                raise ValueError(f"Dataset record {index} exceeds the 100 column limit.")
            cleaned: dict[str, Any] = {}
            for key, value in record.items():
                key_text = str(key).strip()
                if not key_text:
                    raise ValueError(f"Dataset record {index} has an empty column name.")
                if isinstance(value, (dict, list)):
                    value_text: Any = json.dumps(value, ensure_ascii=False, sort_keys=True)
                else:
                    value_text = value
                if len(str(value_text or "")) > MAX_CELL_CHARACTERS:
                    raise ValueError(
                        f"Dataset record {index} has a cell over the 2,000 character limit."
                    )
                cleaned[key_text] = value_text
            normalized = _normalized_row(cleaned)
            record_id = str(
                normalized.get("record_id", normalized.get("case_id", ""))
            ).strip()
            if not record_id:
                raise ValueError(
                    f"Dataset record {index} requires record_id (case_id is accepted "
                    "as an alias)."
                )
            if record_id in seen_record_ids:
                raise ValueError(f"Dataset contains duplicate record_id: {record_id}.")
            seen_record_ids.add(record_id)
            normalized_confidence = _coerce_number(normalized.get("confidence"))
            confidence_supplied = str(normalized.get("confidence", "")).strip() != ""
            if confidence_supplied and normalized_confidence is None:
                raise ValueError(
                    f"Dataset record {index} has a non-finite or invalid confidence."
                )
            if normalized_confidence is not None and not 0 <= normalized_confidence <= 1:
                raise ValueError(
                    f"Dataset record {index} confidence must be between 0 and 1."
                )
            normalized_score = _coerce_number(normalized.get("score"))
            score_supplied = str(normalized.get("score", "")).strip() != ""
            if score_supplied and normalized_score is None:
                raise ValueError(
                    f"Dataset record {index} has a non-finite or invalid score."
                )
            if normalized_score is not None and not 0 <= normalized_score <= 1:
                raise ValueError(f"Dataset record {index} score must be between 0 and 1.")
            if not str(normalized.get("record_id", "")).strip():
                cleaned["record_id"] = record_id
            clean_records.append(cleaned)
        digest = hashlib.sha256(raw_for_hash.encode("utf-8")).hexdigest()
        return clean_records, dataset_format, digest

    @staticmethod
    def _regulatory_source(control_id: str) -> dict[str, Any]:
        item = next(
            source for source in REGULATION_LIBRARY if source["control_id"] == control_id
        )
        return {
            "authority": "law",
            "source_id": item["source_id"],
            "framework": item["framework"],
            "jurisdiction": item["jurisdiction"],
            "provision": item["provision"],
            "title": item["title"],
            "requirement_summary": item["requirement_summary"],
            "official_url": item["official_url"],
            "source_version": item["source_version"],
            "application_or_review_date": item["application_or_review_date"],
            "source_status": item["status"],
        }

    @classmethod
    def _regulatory_result(
        cls,
        control_id: str,
        applicable: bool,
        evidence: list[tuple[str, bool | None]],
        observation: str,
        *,
        readiness: bool = False,
        applicability_note: str,
    ) -> dict[str, Any]:
        source = cls._regulatory_source(control_id)
        evidence_snapshot = {name: value for name, value in evidence}
        if not applicable:
            status = "not_applicable"
            detail = "The row did not meet this demonstration rule's applicability condition."
        elif any(value is None for _, value in evidence):
            status = "insufficient_evidence"
            missing = [name for name, value in evidence if value is None]
            detail = f"Required evidence is missing: {', '.join(missing)}."
        elif all(bool(value) for _, value in evidence):
            status = "future_readiness" if readiness else "pass"
            detail = (
                f"{observation} This is an operational evidence proxy, not a legal "
                "conclusion."
            )
        else:
            status = "readiness_gap" if readiness else "fail"
            detail = (
                f"{observation} This is a potential operational control gap for "
                "qualified review, not a confirmed legal violation."
            )
        return {
            "control_id": control_id,
            "rule_version": RULE_ENGINE_VERSION,
            "source_authority": "law",
            "evaluation_layer": "future_readiness" if readiness else "current_law_proxy",
            "status": status,
            "source": source,
            "evidence": evidence_snapshot,
            "observation": detail,
            "applicability_note": applicability_note,
            "legal_violation_confirmed": False,
        }

    def _evaluate_regulations(self, row: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        data = _normalized_row(row)
        risk = str(data.get("risk_class", "")).strip().lower()
        marked_high_risk = _coerce_bool(data.get("high_risk"))
        high_risk = marked_high_risk is True or risk in {
            "high",
            "high_risk",
            "high-impact",
            "high_impact",
        }
        contains_personal = _coerce_bool(data.get("contains_personal_data"))
        decision_mode = str(data.get("decision_mode", "")).strip().lower()
        significant = _coerce_bool(data.get("significant_effect"))
        art22_applicable = decision_mode in {"automated", "solely_automated"} and significant is True
        ai_act_role = str(data.get("ai_act_role", "")).strip().lower()
        deployer_candidate = high_risk and ai_act_role in {"", "deployer"}
        role_evidence = True if ai_act_role == "deployer" else None
        current_law = [
            self._regulatory_result(
                "REG-DAT-001",
                contains_personal is True,
                [
                    (
                        "processing_purpose_documented",
                        _coerce_bool(data.get("processing_purpose_documented")),
                    ),
                    ("data_necessary", _coerce_bool(data.get("data_necessary"))),
                    ("data_minimized", _coerce_bool(data.get("data_minimized"))),
                ],
                "Purpose, necessity and minimisation evidence is recorded for the row.",
                applicability_note=(
                    "Selected when contains_personal_data=true. The values are uploaded "
                    "evidence assertions and require assurance outside this prototype."
                ),
            ),
            self._regulatory_result(
                "REG-AUT-001",
                art22_applicable,
                [
                    (
                        "art22_exception_documented",
                        _coerce_bool(data.get("art22_exception_documented")),
                    ),
                    ("human_intervention_available", _coerce_bool(data.get("human_intervention_available"))),
                    ("contestability_available", _coerce_bool(data.get("contestability_available"))),
                ],
                "A documented condition plus human-intervention and contestability indicators are present.",
                applicability_note=(
                    "Selected only for rows marked solely/fully automated and "
                    "significant. The engine does not decide whether an Article 22(2) "
                    "condition is legally sufficient."
                ),
            ),
        ]
        future_readiness = [
            self._regulatory_result(
                "READY-DEP-001",
                deployer_candidate,
                [
                    ("ai_act_role_is_deployer", role_evidence),
                    (
                        "instructions_for_use_followed",
                        _coerce_bool(data.get("instructions_for_use_followed")),
                    ),
                    (
                        "human_oversight_available",
                        _coerce_bool(data.get("human_oversight_available")),
                    ),
                    (
                        "oversight_person_competent",
                        _coerce_bool(data.get("oversight_person_competent")),
                    ),
                ],
                "The uploaded evidence supports this staged deployer-readiness mapping.",
                readiness=True,
                applicability_note=(
                    "A self-declared high-impact/high-risk label is treated only as a "
                    "candidate. Qualified review must confirm AI Act classification, "
                    "role and applicable date."
                ),
            )
        ]
        return {"current_law": current_law, "future_readiness": future_readiness}

    @staticmethod
    def _condition_matches(
        row: dict[str, Any], condition: dict[str, Any]
    ) -> tuple[bool | None, dict[str, Any]]:
        field = str(condition["field"])
        raw = row.get(field)
        operator = condition["operator"]
        expected = condition["value"]
        evidence = {"field": field, "observed": raw, "operator": operator, "expected": expected}
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return None, evidence
        if operator == "less_than":
            number = _coerce_number(raw)
            return (None if number is None else number < float(expected)), evidence
        if operator == "in":
            return str(raw).strip().lower() in {str(item).lower() for item in expected}, evidence
        return None, evidence

    def _evaluate_internal_policy(
        self, row: dict[str, Any], policy: dict[str, Any]
    ) -> list[dict[str, Any]]:
        data = _normalized_row(row)
        results: list[dict[str, Any]] = []
        for rule in policy["rules"]:
            if rule.get("activation_status") != "active":
                continue
            matches: list[bool | None] = []
            condition_evidence: list[dict[str, Any]] = []
            for condition in rule["conditions"]:
                matched, evidence = self._condition_matches(data, condition)
                matches.append(matched)
                condition_evidence.append(evidence)
            if any(item is False for item in matches):
                status = "not_applicable"
                observation = "The row does not meet the internal clause condition."
            elif any(item is None for item in matches):
                status = "insufficient_evidence"
                observation = "The row lacks evidence needed to determine policy applicability."
            else:
                evidence_field = rule["requirement"]["evidence_field"]
                review_evidence = data.get(evidence_field, data.get("human_review"))
                completed = _coerce_bool(review_evidence)
                if completed is True:
                    status = "pass"
                    observation = "Required manual review is recorded as complete."
                else:
                    status = "manual_review"
                    observation = (
                        "Regulatory checks may pass, but the stricter company clause "
                        "requires manual review before this record can proceed."
                    )
            results.append(
                {
                    "control_id": rule["rule_id"],
                    "rule_version": rule["rule_version"],
                    "source_authority": "internal_policy",
                    "status": status,
                    "source": {
                        "authority": "internal_policy",
                        "source_id": policy["policy_id"],
                        "framework": "Company policy",
                        "jurisdiction": "Organisation-specific",
                        "provision": rule["clause_id"],
                        "title": policy["name"],
                        "requirement_summary": rule["description"],
                        "official_url": None,
                        "source_version": policy["version"],
                        "source_status": policy["status"],
                        "source_clause": rule["source_clause"],
                        "source_clause_sha256": rule["source_clause_sha256"],
                        "source_locator": rule["source_locator"],
                        "source_sha256": policy["source_sha256"],
                    },
                    "evidence": {
                        "conditions": condition_evidence,
                        "manual_review_completed": _coerce_bool(
                            data.get("manual_review_completed", data.get("human_review"))
                        ),
                    },
                    "observation": observation,
                    "legal_violation_confirmed": False,
                }
            )
        return results

    @staticmethod
    def _finding(result: dict[str, Any], row_number: int, record_id: str) -> dict[str, Any]:
        authority = result["source_authority"]
        status = result["status"]
        if authority == "law":
            if status == "fail":
                finding_type = "potential_regulatory_control_gap"
            elif status == "readiness_gap":
                finding_type = "future_readiness_gap"
            else:
                finding_type = "regulatory_evidence_review_required"
        else:
            finding_type = (
                "internal_policy_manual_review"
                if status == "manual_review"
                else "internal_policy_evidence_review_required"
            )
        return {
            "finding_id": _identifier("ROWFND"),
            "row_number": row_number,
            "record_id": record_id,
            "finding_type": finding_type,
            "status": "open",
            "result_status": status,
            "control_id": result["control_id"],
            "source_authority": authority,
            "citation": {
                "source_id": result["source"]["source_id"],
                "provision": result["source"]["provision"],
                "source_version": result["source"]["source_version"],
                "official_url": result["source"].get("official_url"),
                "source_clause": result["source"].get("source_clause"),
                "source_clause_sha256": result["source"].get(
                    "source_clause_sha256"
                ),
                "source_locator": result["source"].get("source_locator"),
                "application_or_review_date": result["source"].get(
                    "application_or_review_date"
                ),
            },
            "observation": result["observation"],
            "legal_violation_confirmed": False,
        }

    @staticmethod
    def _model_statistics(records: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate transparent descriptive metrics from the uploaded rows."""

        normalized = [_normalized_row(item) for item in records]
        confidences = [
            number
            for item in normalized
            if (number := _coerce_number(item.get("confidence"))) is not None
        ]
        if confidences:
            confidence_statistics: dict[str, Any] = {
                "status": "calculated",
                "denominator": len(confidences),
                "mean": sum(confidences) / len(confidences),
                "minimum": min(confidences),
                "maximum": max(confidences),
                "definition": "Arithmetic mean/minimum/maximum of non-empty confidence values.",
            }
        else:
            confidence_statistics = {
                "status": "not_calculated",
                "denominator": 0,
                "reason": "No numeric confidence values were supplied.",
            }

        labelled = [
            item
            for item in normalized
            if str(item.get("predicted_label", "")).strip()
            and str(item.get("actual_label", "")).strip()
        ]
        if labelled:
            errors = sum(
                str(item["predicted_label"]).strip().lower()
                != str(item["actual_label"]).strip().lower()
                for item in labelled
            )
            error_rate: dict[str, Any] = {
                "status": "calculated",
                "denominator": len(labelled),
                "errors": errors,
                "value": errors / len(labelled),
                "definition": (
                    "Rows where normalized predicted_label differs from actual_label, "
                    "divided by rows containing both labels."
                ),
            }
        else:
            error_rate = {
                "status": "not_calculated",
                "denominator": 0,
                "reason": "Both predicted_label and actual_label are required.",
            }

        grouped: dict[str, dict[str, int]] = {}
        for item in normalized:
            group = str(item.get("protected_group", "")).strip()
            adverse = _coerce_bool(item.get("adverse_action"))
            if not group or adverse is None:
                continue
            group_counts = grouped.setdefault(group, {"records": 0, "adverse_actions": 0})
            group_counts["records"] += 1
            group_counts["adverse_actions"] += int(adverse)
        group_rows = [
            {
                "group": group,
                **counts,
                "adverse_action_rate": counts["adverse_actions"] / counts["records"],
            }
            for group, counts in sorted(grouped.items())
        ]
        if group_rows:
            rates = [item["adverse_action_rate"] for item in group_rows]
            group_statistics: dict[str, Any] = {
                "status": "calculated",
                "eligible_records": sum(item["records"] for item in group_rows),
                "groups": group_rows,
                "maximum_rate_gap": max(rates) - min(rates) if len(rates) > 1 else None,
                "definition": (
                    "For each supplied protected_group, true adverse_action rows divided "
                    "by rows in that group. The maximum rate gap is descriptive and is "
                    "not itself a legal or fairness threshold."
                ),
            }
        else:
            group_statistics = {
                "status": "not_calculated",
                "eligible_records": 0,
                "reason": "protected_group and boolean adverse_action are required.",
            }

        populations: dict[str, list[float]] = {"baseline": [], "current": []}
        for item in normalized:
            population = str(item.get("population", "")).strip().lower()
            score = _coerce_number(item.get("score"))
            if population in populations and score is not None:
                populations[population].append(score)
        if populations["baseline"] and populations["current"]:
            edges = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0000001)
            distributions: dict[str, list[float]] = {}
            for population, values in populations.items():
                counts = [0] * 5
                for value in values:
                    bucket = min(int(value * 5), 4)
                    counts[bucket] += 1
                distributions[population] = [count / len(values) for count in counts]
            epsilon = 1e-6
            psi_value = sum(
                (current - baseline)
                * math.log((current + epsilon) / (baseline + epsilon))
                for baseline, current in zip(
                    distributions["baseline"], distributions["current"], strict=True
                )
            )
            psi: dict[str, Any] = {
                "status": "calculated",
                "baseline_denominator": len(populations["baseline"]),
                "current_denominator": len(populations["current"]),
                "fixed_bin_edges": list(edges[:-1]) + [1.0],
                "baseline_distribution": distributions["baseline"],
                "current_distribution": distributions["current"],
                "value": psi_value,
                "definition": (
                    "Population Stability Index using five fixed score bins and a "
                    "1e-6 smoothing constant. No universal pass threshold is applied."
                ),
            }
        else:
            psi = {
                "status": "not_calculated",
                "baseline_denominator": len(populations["baseline"]),
                "current_denominator": len(populations["current"]),
                "reason": "score rows labelled baseline and current are both required.",
            }
        return {
            "confidence": confidence_statistics,
            "observed_error_rate": error_rate,
            "group_adverse_action_rates": group_statistics,
            "population_stability_index": psi,
            "interpretation_notice": (
                "These statistics are calculated from uploaded synthetic records and "
                "are reported with exact denominators. They are not compliance scores."
            ),
        }

    def run_dataset(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._require_synthetic(payload, "synthetic_data_confirmed")
        records, dataset_format, dataset_hash = self._parse_dataset(payload)
        name = str(payload.get("name", "Synthetic governance dataset")).strip()
        filename = Path(str(payload.get("filename", f"dataset.{dataset_format}"))).name
        requested_policy_ids = payload.get("policy_ids")
        if requested_policy_ids is None:
            policies = [item for item in self.policies.values() if item["status"] == "active"]
        else:
            if not isinstance(requested_policy_ids, list):
                raise ValueError("policy_ids must be an array.")
            policies = []
            for policy_id in requested_policy_ids:
                policy = self.policies.get(str(policy_id))
                if policy is None:
                    raise ValueError(f"Unknown internal policy: {policy_id}.")
                if policy["status"] != "active":
                    raise ValueError(f"Internal policy {policy_id} must be activated before use.")
                policies.append(policy)

        row_results: list[dict[str, Any]] = []
        all_regulatory: list[dict[str, Any]] = []
        all_future_readiness: list[dict[str, Any]] = []
        all_internal: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []
        for row_number, raw_row in enumerate(records, start=1):
            row = _normalized_row(raw_row)
            record_id = str(row["record_id"]).strip()
            regulatory_layers = self._evaluate_regulations(row)
            regulatory = regulatory_layers["current_law"]
            future_readiness = regulatory_layers["future_readiness"]
            internal = [
                result
                for policy in policies
                for result in self._evaluate_internal_policy(row, policy)
            ]
            all_regulatory.extend(regulatory)
            all_future_readiness.extend(future_readiness)
            all_internal.extend(internal)
            row_findings = [
                self._finding(result, row_number, record_id)
                for result in regulatory + future_readiness + internal
                if result["status"]
                in {"fail", "readiness_gap", "manual_review", "insufficient_evidence"}
            ]
            findings.extend(row_findings)
            statuses = {
                item["status"] for item in regulatory + future_readiness + internal
            }
            if "fail" in statuses:
                disposition = "action_required"
            elif "manual_review" in statuses:
                disposition = "manual_review"
            elif "insufficient_evidence" in statuses:
                disposition = "insufficient_evidence"
            elif "readiness_gap" in statuses:
                disposition = "allow_with_controls"
            elif all(
                item["status"] == "not_applicable"
                for item in regulatory + future_readiness + internal
            ):
                disposition = "not_assessed"
            else:
                disposition = "pass"
            row_results.append(
                {
                    "row_number": row_number,
                    "record_id": record_id,
                    "disposition": disposition,
                    "regulatory_outcome": (
                        "potential_control_gap"
                        if any(item["status"] == "fail" for item in regulatory)
                        else "insufficient_evidence"
                        if any(item["status"] == "insufficient_evidence" for item in regulatory)
                        else "not_assessed"
                        if all(item["status"] == "not_applicable" for item in regulatory)
                        else "pass"
                    ),
                    "future_readiness_outcome": (
                        "readiness_gap"
                        if any(
                            item["status"] == "readiness_gap"
                            for item in future_readiness
                        )
                        else "insufficient_evidence"
                        if any(
                            item["status"] == "insufficient_evidence"
                            for item in future_readiness
                        )
                        else "not_assessed"
                        if all(
                            item["status"] == "not_applicable"
                            for item in future_readiness
                        )
                        else "ready"
                    ),
                    "internal_policy_outcome": (
                        "manual_review"
                        if any(item["status"] == "manual_review" for item in internal)
                        else "insufficient_evidence"
                        if any(item["status"] == "insufficient_evidence" for item in internal)
                        else "pass"
                        if internal
                        else "not_evaluated"
                    ),
                    "evidence_snapshot": {
                        key: row.get(key)
                        for key in (
                            "domain",
                            "risk_class",
                            "high_risk",
                            "ai_act_role",
                            "decision_mode",
                            "confidence",
                            "instructions_for_use_followed",
                            "human_oversight_available",
                            "oversight_person_competent",
                            "contains_personal_data",
                            "processing_purpose_documented",
                            "data_necessary",
                            "data_minimized",
                            "significant_effect",
                            "art22_exception_documented",
                            "human_intervention_available",
                            "contestability_available",
                            "manual_review_completed",
                            "human_review",
                            "protected_group",
                            "adverse_action",
                            "predicted_label",
                            "actual_label",
                            "population",
                            "score",
                        )
                        if key in row
                    },
                    "control_results": regulatory + future_readiness + internal,
                    "findings": row_findings,
                    "legal_violation_confirmed": False,
                }
            )

        regulatory_counts = _status_counts(all_regulatory)
        readiness_counts = _readiness_counts(all_future_readiness)
        internal_counts = _status_counts(all_internal)
        dispositions = [item["disposition"] for item in row_results]
        if "action_required" in dispositions:
            overall = "action_required"
        elif "manual_review" in dispositions:
            overall = "manual_review"
        elif "insufficient_evidence" in dispositions:
            overall = "insufficient_evidence"
        elif "allow_with_controls" in dispositions:
            overall = "allow_with_controls"
        elif all(item == "not_assessed" for item in dispositions):
            overall = "not_assessed"
        else:
            overall = "pass"
        pass_then_review = sum(
            item["regulatory_outcome"] == "pass"
            and item["internal_policy_outcome"] == "manual_review"
            for item in row_results
        )
        run_id = _identifier("RUN")
        created_at = _now()
        columns = sorted({str(key) for row in records for key in row})
        run = {
            "schema": "styrai.dataset-governance-run.v1",
            "run_id": run_id,
            "created_at": created_at,
            "status": "completed",
            "mode": "synthetic_local_evaluation",
            "model_id": str(payload.get("model_id", "uploaded-model-output"))[:160],
            "dataset": {
                "name": name[:160],
                "filename": filename[:160],
                "format": dataset_format,
                "schema_version": DATASET_SCHEMA_VERSION,
                "sha256": dataset_hash,
                "records_evaluated": len(records),
                "columns": columns,
                "synthetic_confirmed": True,
                "raw_dataset_written_to_disk": False,
            },
            "rule_set": {
                "engine_version": RULE_ENGINE_VERSION,
                "regulation_library_version": REGULATION_LIBRARY_VERSION,
                "regulation_source_versions": [
                    {
                        "source_id": item["source_id"],
                        "provision": item["provision"],
                        "source_version": item["source_version"],
                        "status": item["status"],
                    }
                    for item in REGULATION_LIBRARY
                ],
                "internal_policies": [
                    {
                        "policy_id": item["policy_id"],
                        "name": item["name"],
                        "version": item["version"],
                        "source_sha256": item["source_sha256"],
                        "active_rule_ids": item["active_rule_ids"],
                    }
                    for item in policies
                ],
            },
            "summary": {
                "overall_disposition": overall,
                "records_evaluated": len(records),
                "records_passed": dispositions.count("pass"),
                "records_action_required": dispositions.count("action_required"),
                "records_manual_review": dispositions.count("manual_review"),
                "records_insufficient_evidence": dispositions.count("insufficient_evidence"),
                "records_allow_with_controls": dispositions.count("allow_with_controls"),
                "records_not_assessed": dispositions.count("not_assessed"),
                "regulatory_controls": regulatory_counts,
                "future_readiness_controls": readiness_counts,
                "internal_policy_controls": internal_counts,
                "regulation_pass_internal_review": pass_then_review,
                "percentage_score_used": False,
                "statistics_definition": (
                    "Record dispositions use the strictest applicable result. Control "
                    "counts are explicit record-by-control outcomes; no percentage is "
                    "treated as legal compliance. Future AI Act readiness is excluded "
                    "from current-law proxy pass/fail counts."
                ),
                "legal_violation_confirmed": False,
            },
            "model_statistics": self._model_statistics(records),
            "findings": findings,
            "row_results": row_results,
            "disclaimer": (
                "Synthetic deterministic control evaluation. Findings identify "
                "potential control gaps or internal review requirements, not legal "
                "violations or legal advice."
            ),
        }
        self.runs[run_id] = run
        self.audit_log.append(
            "governance.dataset_run_completed",
            run_id,
            {
                "run_id": run_id,
                "created_at": created_at,
                "dataset": run["dataset"],
                "rule_set": run["rule_set"],
                "summary": run["summary"],
                "finding_ids": [item["finding_id"] for item in findings],
                "raw_dataset_stored": False,
            },
        )
        return run

    def list_runs(self) -> list[dict[str, Any]]:
        return list(reversed(list(self.runs.values())))

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self.runs.get(run_id)
        if run is None:
            raise ValueError("Unknown dataset governance run.")
        return run

    def evidence(self, object_id: str) -> dict[str, Any]:
        subject = self.runs.get(object_id) or self.policies.get(object_id)
        if subject is None:
            raise ValueError("Unknown dataset or policy evidence object.")
        related_ids = {object_id}
        if object_id in self.runs:
            related_ids.update(
                item["policy_id"]
                for item in subject["rule_set"]["internal_policies"]
            )
            related_ids.update(item["finding_id"] for item in subject["findings"])
        records = [
            record
            for record in self.audit_log.records()
            if record["action_id"] in related_ids
            or str(record["payload"].get("run_id", "")) in related_ids
            or str(record["payload"].get("policy_id", "")) in related_ids
        ]
        try:
            audit_valid = self.audit_log.verify()
        except AuditIntegrityError:
            audit_valid = False
        return {
            "schema": "styrai.dataset-governance-evidence.v1",
            "generated_at": _now(),
            "subject_id": object_id,
            "subject": subject,
            "regulation_library": public_regulation_library(),
            "audit_records": records,
            "audit_chain_valid": audit_valid,
            "legal_violation_confirmed": False,
            "disclaimer": "Synthetic demonstration evidence; not legal certification.",
        }
