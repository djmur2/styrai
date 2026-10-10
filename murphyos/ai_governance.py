"""Executable AI-governance control plane used by the StyrAI demonstration.

The engine is intentionally deterministic and local.  It models the controls
that sit around deployed AI systems: inventory and model passports, regulatory
control assessments, an outbound prompt firewall, production monitoring,
incidents, findings, and reconstructable evidence.  It does not call a real AI
provider and does not claim that a model or organisation is legally compliant.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from .audit import AuditIntegrityError, HashChainedAuditLog


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _identifier(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10].upper()}"


SENSITIVITY = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


@dataclass
class ModelDeployment:
    model_id: str
    name: str
    domain: str
    use_case: str
    owner: str
    provider: str
    model_name: str
    version: str
    approved_version: str
    environment: str
    status: str
    external_destination: bool
    region: str
    registered: bool
    approved_data_classes: tuple[str, ...]
    approved_uses: tuple[str, ...]
    risk_class: str
    frameworks: tuple[str, ...]
    monitoring_enabled: bool
    human_oversight: bool
    impact_assessment_current: bool
    independent_validation_current: bool
    dpa_approved: bool
    zero_retention: bool
    fallback_model_id: str | None
    metrics: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for name in ("approved_data_classes", "approved_uses", "frameworks"):
            payload[name] = list(payload[name])
        return payload


@dataclass
class Finding:
    finding_id: str
    created_at: str
    model_id: str
    source: str
    severity: str
    status: str
    title: str
    description: str
    policy_id: str
    framework_mappings: tuple[str, ...]
    required_action: str
    control_action: str
    evidence_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["framework_mappings"] = list(self.framework_mappings)
        return payload


@dataclass
class Assessment:
    assessment_id: str
    created_at: str
    model_id: str
    model_version: str
    result: str
    readiness_score: int
    controls_tested: int
    controls_passed: int
    finding_ids: tuple[str, ...]
    control_results: tuple[dict[str, Any], ...]
    disclaimer: str = "Control assessment for demonstration; not legal certification."

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["finding_ids"] = list(self.finding_ids)
        payload["control_results"] = list(self.control_results)
        return payload


@dataclass
class RuntimeInspection:
    event_id: str
    created_at: str
    model_id: str
    effective_model_id: str | None
    actor: str
    use_case: str
    declared_classification: str
    effective_classification: str
    detected_types: tuple[str, ...]
    destination: str
    decision: str
    reason: str
    policy_ids: tuple[str, ...]
    redaction_count: int
    safe_preview: str
    prompt_hash: str
    transmission_prevented: bool
    raw_input_stored: bool = False

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["detected_types"] = list(self.detected_types)
        payload["policy_ids"] = list(self.policy_ids)
        return payload


@dataclass
class GovernanceIncident:
    incident_id: str
    created_at: str
    model_id: str
    event_id: str
    severity: str
    category: str
    status: str
    title: str
    response_actions: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["response_actions"] = list(self.response_actions)
        return payload


@dataclass(frozen=True)
class DetectionRule:
    data_type: str
    classification: str
    expression: re.Pattern[str]
    replacement: str


DETECTION_RULES = (
    DetectionRule(
        "credential_or_secret",
        "restricted",
        re.compile(
            r"(?i)\b(?:api[_ -]?key|access[_ -]?token|password|secret)\s*[:=]\s*[^\s,;]+"
        ),
        "[REDACTED SECRET]",
    ),
    DetectionRule(
        "norwegian_national_identity_number",
        "restricted",
        re.compile(r"(?<!\d)\d{11}(?!\d)"),
        "[REDACTED NATIONAL ID]",
    ),
    DetectionRule(
        "clinical_record_identifier",
        "restricted",
        re.compile(
            r"(?i)\b(?:mrn|patient[_ -]?id)\s*[:#=]\s*[A-Z0-9][A-Z0-9-]{3,24}\b"
        ),
        "[REDACTED CLINICAL ID]",
    ),
    DetectionRule(
        "payment_card_number",
        "restricted",
        re.compile(r"(?<![A-Za-z0-9])(?:\d[ -]*?){13,19}(?!\d)"),
        "[REDACTED PAYMENT CARD]",
    ),
    DetectionRule(
        "bank_account_or_iban",
        "confidential",
        re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9 ]{10,30}\b"),
        "[REDACTED BANK ACCOUNT]",
    ),
    DetectionRule(
        "email_address",
        "confidential",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED EMAIL]",
    ),
    DetectionRule(
        "corporate_confidential_marker",
        "confidential",
        re.compile(r"(?i)\b(?:confidential|trade secret|inside information|privileged)\b"),
        "[CONFIDENTIAL]",
    ),
)


CONTROL_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "control_id": "INV-001",
        "name": "Registered AI system and accountable owner",
        "mappings": ("EU AI Act Art. 9", "ISO/IEC 42001 A.6", "NIST AI RMF GOVERN"),
    },
    {
        "control_id": "USE-001",
        "name": "Approved model, version and intended use",
        "mappings": ("EU AI Act Arts. 9 and 15", "NIST AI RMF MAP"),
    },
    {
        "control_id": "DATA-001",
        "name": "Outbound data classification and minimisation",
        "mappings": ("GDPR Arts. 5, 25 and 32", "DORA Arts. 6 and 9"),
    },
    {
        "control_id": "HUM-001",
        "name": "Human oversight for high-impact use",
        "mappings": ("EU AI Act Art. 14", "NIST AI RMF GOVERN"),
    },
    {
        "control_id": "VAL-001",
        "name": "Independent validation and impact assessment",
        "mappings": ("EU AI Act Arts. 9 and 10", "GDPR Art. 35", "NIST AI RMF MEASURE"),
    },
    {
        "control_id": "MON-001",
        "name": "Production performance, bias and drift monitoring",
        "mappings": ("EU AI Act Arts. 12 and 15", "DORA Art. 11", "NIST AI RMF MANAGE"),
    },
)


class AIGovernanceControlPlane:
    """Stateful local control plane for deployed-model governance."""

    def __init__(self, audit_log: HashChainedAuditLog) -> None:
        self.audit_log = audit_log
        self.models = {model.model_id: model for model in self._seed_models()}
        self.assessments: dict[str, Assessment] = {}
        self.findings: dict[str, Finding] = {}
        self.events: dict[str, RuntimeInspection] = {}
        self.monitoring_events: dict[str, dict[str, Any]] = {}
        self.version_events: dict[str, dict[str, Any]] = {}
        self.incidents: dict[str, GovernanceIncident] = {}
        self._seed_assessments()

    @staticmethod
    def _seed_models() -> tuple[ModelDeployment, ...]:
        return (
            ModelDeployment(
                "finance-credit-risk-prod",
                "Retail Credit Risk Decision Support",
                "financial_services",
                "credit_risk_decision_support",
                "Head of Credit Model Risk",
                "Customer-hosted model service",
                "Credit gradient-boosting ensemble",
                "12.4",
                "12.4",
                "production",
                "approved_with_conditions",
                False,
                "Norway",
                True,
                ("internal", "confidential", "restricted"),
                ("credit_risk_decision_support",),
                "high_impact",
                ("EU AI Act", "GDPR", "DORA", "EBA model-risk expectations"),
                True,
                True,
                True,
                False,
                True,
                True,
                "secure-enterprise-llm",
                {"drift_score": 0.06, "bias_gap": 0.03, "error_rate": 0.012},
            ),
            ModelDeployment(
                "healthcare-summary-prod",
                "Clinical Visit Summary Copilot",
                "healthcare",
                "clinician_reviewed_visit_summary",
                "Director of Clinical Informatics",
                "Customer-hosted clinical AI environment",
                "Clinical summary language model",
                "2026.08.2",
                "2026.08.2",
                "production",
                "approved",
                False,
                "Norway",
                True,
                ("internal", "confidential", "restricted"),
                ("clinician_reviewed_visit_summary",),
                "high_impact",
                ("EU AI Act", "GDPR", "clinical quality management"),
                True,
                True,
                True,
                True,
                True,
                True,
                "secure-enterprise-llm",
                {"drift_score": 0.03, "groundedness": 0.985, "error_rate": 0.006},
            ),
            ModelDeployment(
                "corporate-copilot-external",
                "Corporate Knowledge Copilot",
                "enterprise",
                "knowledge_and_drafting",
                "Director of Digital Workplace",
                "Approved external zero-retention gateway",
                "Enterprise language model",
                "2026-09",
                "2026-09",
                "production",
                "approved",
                True,
                "EU/EEA",
                True,
                ("public", "internal", "confidential"),
                ("knowledge_and_drafting", "customer_service_drafting"),
                "limited",
                ("EU AI Act", "GDPR", "DORA", "ISO/IEC 42001"),
                True,
                True,
                True,
                True,
                True,
                True,
                "secure-enterprise-llm",
                {"drift_score": 0.04, "groundedness": 0.94, "error_rate": 0.009},
            ),
            ModelDeployment(
                "secure-enterprise-llm",
                "Restricted Data AI Enclave",
                "enterprise",
                "approved_restricted_processing",
                "Chief Information Security Officer",
                "Customer-controlled private inference",
                "Private language model",
                "4.3",
                "4.3",
                "production",
                "approved",
                False,
                "Norway",
                True,
                ("public", "internal", "confidential", "restricted"),
                ("approved_restricted_processing", "knowledge_and_drafting"),
                "limited",
                ("GDPR", "DORA", "ISO/IEC 42001"),
                True,
                True,
                True,
                True,
                True,
                True,
                None,
                {"drift_score": 0.02, "groundedness": 0.96, "error_rate": 0.007},
            ),
            ModelDeployment(
                "shadow-consumer-ai",
                "Unapproved Consumer AI Site",
                "enterprise",
                "unknown",
                "Unassigned",
                "Unknown public service",
                "Unknown",
                "unverified",
                "none",
                "discovered",
                "blocked",
                True,
                "Unknown",
                False,
                (),
                (),
                "prohibited",
                ("GDPR", "DORA", "corporate AI policy"),
                False,
                False,
                False,
                False,
                False,
                False,
                None,
                {},
            ),
        )

    def _seed_assessments(self) -> None:
        # Seeding is silent: the visible audit trail starts with user/demo actions.
        for model_id in self.models:
            self.assess_model(model_id, record_audit=False)

    def _new_finding(
        self,
        *,
        model_id: str,
        source: str,
        severity: str,
        title: str,
        description: str,
        policy_id: str,
        mappings: tuple[str, ...],
        required_action: str,
        control_action: str,
        evidence_ref: str,
        record_audit: bool = True,
    ) -> Finding:
        finding = Finding(
            finding_id=_identifier("FND"),
            created_at=_now(),
            model_id=model_id,
            source=source,
            severity=severity,
            status="open",
            title=title,
            description=description,
            policy_id=policy_id,
            framework_mappings=mappings,
            required_action=required_action,
            control_action=control_action,
            evidence_ref=evidence_ref,
        )
        self.findings[finding.finding_id] = finding
        if record_audit:
            self.audit_log.append(
                "governance.finding_opened", finding.finding_id, finding.as_dict()
            )
        return finding

    @staticmethod
    def _control_result(
        control_id: str,
        passed: bool,
        observation: str,
    ) -> dict[str, Any]:
        control = next(
            item for item in CONTROL_CATALOG if item["control_id"] == control_id
        )
        return {
            "control_id": control_id,
            "control": control["name"],
            "status": "pass" if passed else "fail",
            "observation": observation,
            "framework_mappings": list(control["mappings"]),
        }

    def assess_model(
        self, model_id: str, *, record_audit: bool = True
    ) -> dict[str, Any]:
        model = self.models.get(model_id)
        if model is None:
            raise ValueError("Unknown deployed AI model.")

        results = (
            self._control_result(
                "INV-001",
                model.registered and model.owner not in {"", "Unassigned"},
                "Inventory registration and accountable owner are present."
                if model.registered and model.owner not in {"", "Unassigned"}
                else "The destination is not registered with an accountable owner.",
            ),
            self._control_result(
                "USE-001",
                model.status in {"approved", "approved_with_conditions"}
                and model.version == model.approved_version,
                "Runtime version matches the approved model passport."
                if model.version == model.approved_version
                else "Observed runtime version does not match the approved passport.",
            ),
            self._control_result(
                "DATA-001",
                not model.external_destination
                or (model.dpa_approved and model.zero_retention),
                "Destination and retention controls satisfy the outbound-data policy."
                if not model.external_destination
                or (model.dpa_approved and model.zero_retention)
                else "External destination lacks approved data-processing or retention terms.",
            ),
            self._control_result(
                "HUM-001",
                model.risk_class != "high_impact" or model.human_oversight,
                "Required human oversight is recorded."
                if model.risk_class != "high_impact" or model.human_oversight
                else "High-impact use lacks an effective human-oversight control.",
            ),
            self._control_result(
                "VAL-001",
                model.risk_class != "high_impact"
                or (
                    model.impact_assessment_current
                    and model.independent_validation_current
                ),
                "Impact assessment and independent validation are current."
                if model.risk_class != "high_impact"
                or (
                    model.impact_assessment_current
                    and model.independent_validation_current
                )
                else "Independent validation or the impact assessment is not current.",
            ),
            self._control_result(
                "MON-001",
                model.monitoring_enabled,
                "Production telemetry is connected to policy thresholds."
                if model.monitoring_enabled
                else "Continuous production monitoring is not connected.",
            ),
        )
        failed = [item for item in results if item["status"] == "fail"]
        assessment_id = _identifier("ASM")
        finding_ids: list[str] = []
        for item in failed:
            severity = (
                "critical"
                if item["control_id"] in {"INV-001", "DATA-001"}
                and model.external_destination
                else "high"
            )
            finding = self._new_finding(
                model_id=model.model_id,
                source="compliance_assessment",
                severity=severity,
                title=f"{item['control']} failed",
                description=item["observation"],
                policy_id=item["control_id"],
                mappings=tuple(item["framework_mappings"]),
                required_action="Close the control gap and rerun the model assessment.",
                control_action=(
                    "block"
                    if item["control_id"] in {"INV-001", "USE-001", "DATA-001"}
                    else "guard"
                ),
                evidence_ref=assessment_id,
                record_audit=record_audit,
            )
            finding_ids.append(finding.finding_id)

        score = round(100 * (len(results) - len(failed)) / len(results))
        result = "pass" if not failed else "action_required"
        assessment = Assessment(
            assessment_id=assessment_id,
            created_at=_now(),
            model_id=model.model_id,
            model_version=model.version,
            result=result,
            readiness_score=score,
            controls_tested=len(results),
            controls_passed=len(results) - len(failed),
            finding_ids=tuple(finding_ids),
            control_results=tuple(results),
        )
        self.assessments[assessment.assessment_id] = assessment
        if record_audit:
            self.audit_log.append(
                "governance.model_assessed",
                assessment.assessment_id,
                assessment.as_dict(),
            )
        return {
            "assessment": assessment.as_dict(),
            "findings": [self.findings[item].as_dict() for item in finding_ids],
            "model": model.as_dict(),
            "owner": model.owner,
            "containment_status": (
                "blocked"
                if any(
                    self.findings[item].control_action == "block"
                    for item in finding_ids
                )
                else "guarded"
                if finding_ids
                else "approved"
            ),
            "policy_breaches": [item["control_id"] for item in failed],
            "regulatory_obligations_at_risk": sorted(
                {
                    mapping
                    for item in failed
                    for mapping in item["framework_mappings"]
                }
            ),
            "legal_violation_confirmed": False,
        }

    @staticmethod
    def _inspect_text(prompt: str) -> tuple[str, tuple[str, ...], int, str]:
        effective = "public"
        detected: list[str] = []
        safe_text = prompt
        count = 0
        for rule in DETECTION_RULES:
            matches = list(rule.expression.finditer(safe_text))
            if not matches:
                continue
            detected.append(rule.data_type)
            count += len(matches)
            if SENSITIVITY[rule.classification] > SENSITIVITY[effective]:
                effective = rule.classification
            safe_text = rule.expression.sub(rule.replacement, safe_text)
        safe_text = " ".join(safe_text.split())
        return effective, tuple(detected), count, safe_text

    def inspect_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
        model_id = str(payload.get("model_id", "")).strip()
        model = self.models.get(model_id)
        if model is None:
            raise ValueError("Unknown deployed AI model.")
        prompt = str(payload.get("prompt", ""))
        if not prompt.strip():
            raise ValueError("Prompt content is required for inspection.")
        if len(prompt) > 20_000:
            raise ValueError("Prompt content exceeds the demonstration limit.")
        actor = str(payload.get("actor", "demo-employee")).strip() or "demo-employee"
        use_case = str(payload.get("use_case", model.use_case)).strip()
        declared = str(payload.get("classification", "internal")).strip()
        if declared not in SENSITIVITY:
            raise ValueError("Unknown data classification.")

        detected_class, detected, redaction_count, safe_text = self._inspect_text(
            prompt
        )
        effective = max(
            (declared, detected_class), key=lambda value: SENSITIVITY[value]
        )
        decision = "allow"
        effective_model_id: str | None = model.model_id
        reason = "Approved model passport, intended use and data policy matched."
        policies = ["INV-001", "USE-001", "DATA-001"]
        provider_payload: str | None = prompt

        if not model.registered or model.status == "blocked":
            decision = "block"
            reason = "Unregistered or blocked AI destinations fail closed."
        elif model.version != model.approved_version:
            decision = "block"
            reason = "The deployed version does not match the approved model passport."
        elif use_case not in model.approved_uses:
            decision = "block"
            reason = "The requested use is outside the model's approved purpose."
        elif "credential_or_secret" in detected:
            decision = "block"
            reason = "Credentials and secrets are prohibited in every AI destination."
        elif effective == "restricted" and model.external_destination:
            fallback = self.models.get(model.fallback_model_id or "")
            if (
                fallback is not None
                and fallback.status == "approved"
                and "restricted" in fallback.approved_data_classes
            ):
                decision = "route"
                effective_model_id = fallback.model_id
                reason = (
                    "Restricted information was prevented from reaching the external "
                    "provider and routed to the approved private AI enclave."
                )
                provider_payload = safe_text
                policies.append("ROUTE-001")
            else:
                decision = "block"
                effective_model_id = None
                reason = "Restricted information cannot be sent to an external AI system."
        elif effective not in model.approved_data_classes:
            decision = "block"
            effective_model_id = None
            reason = "The model passport does not permit this data classification."
        elif (
            effective == "confidential"
            and model.external_destination
            and (not model.dpa_approved or not model.zero_retention)
        ):
            decision = "block"
            effective_model_id = None
            reason = "The external provider lacks approved processing and retention terms."
        elif redaction_count and effective in {"confidential", "restricted"}:
            decision = "redact"
            reason = "Sensitive fields were removed before permitted model processing."
            provider_payload = safe_text

        if decision == "block":
            provider_payload = None

        event = RuntimeInspection(
            event_id=_identifier("EVT"),
            created_at=_now(),
            model_id=model.model_id,
            effective_model_id=effective_model_id,
            actor=actor,
            use_case=use_case,
            declared_classification=declared,
            effective_classification=effective,
            detected_types=detected,
            destination=model.provider,
            decision=decision,
            reason=reason,
            policy_ids=tuple(policies),
            redaction_count=redaction_count,
            safe_preview=safe_text[:320],
            prompt_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            transmission_prevented=decision in {"block", "route"},
        )
        self.events[event.event_id] = event
        self.audit_log.append(
            "governance.prompt_inspected",
            event.event_id,
            event.as_dict(),
        )

        incident: GovernanceIncident | None = None
        finding: Finding | None = None
        if decision == "block":
            incident = self._create_incident(
                model_id=model.model_id,
                event_id=event.event_id,
                severity="critical" if effective == "restricted" else "high",
                category="data_loss_prevention",
                title="AI prompt transmission blocked by policy",
                actions=(
                    "Prevented transmission before the provider boundary",
                    "Stored only a hash and redacted evidence",
                    "Notified the data owner and AI governance queue",
                ),
            )
            finding = self._new_finding(
                model_id=model.model_id,
                source="runtime_policy",
                severity=incident.severity,
                title="Runtime AI-use policy violation",
                description=reason,
                policy_id="DATA-001",
                mappings=("GDPR Arts. 5, 25 and 32", "DORA Arts. 6 and 9"),
                required_action="Review the attempted use and remediate the source workflow.",
                control_action="block",
                evidence_ref=event.event_id,
            )

        effective_model = (
            self.models.get(effective_model_id) if effective_model_id else None
        )
        if decision == "route":
            automated_actions = [
                "Prevented the external-provider transmission",
                "Removed detected sensitive fields",
                "Routed the safe payload to the approved private AI enclave",
            ]
        elif incident is not None:
            automated_actions = list(incident.response_actions)
        elif decision == "redact":
            automated_actions = [
                "Removed detected sensitive fields before provider invocation",
                "Recorded metadata-only governance evidence",
            ]
        else:
            automated_actions = ["Recorded the permitted call decision"]

        return {
            "event": event.as_dict(),
            "decision": decision,
            "provider_payload": provider_payload,
            "provider_invoked": decision != "block",
            "external_provider_invoked": decision in {"allow", "redact"}
            and model.external_destination,
            "routed_to": effective_model_id if decision == "route" else None,
            "destination_trust": {
                "requested_model_id": model.model_id,
                "requested_provider": model.provider,
                "requested_destination": (
                    "external" if model.external_destination else "customer_controlled"
                ),
                "registered": model.registered,
                "passport_status": model.status,
                "version_matches_passport": model.version == model.approved_version,
                "dpa_approved": model.dpa_approved,
                "zero_retention": model.zero_retention,
                "effective_model_id": effective_model_id,
                "effective_provider": (
                    effective_model.provider if effective_model is not None else None
                ),
            },
            "control_ids": list(event.policy_ids),
            "evidence_id": event.event_id,
            "automated_actions": automated_actions,
            "incident": incident.as_dict() if incident else None,
            "finding": finding.as_dict() if finding else None,
            "raw_input_stored": False,
            "legal_violation_confirmed": False,
        }

    def _create_incident(
        self,
        *,
        model_id: str,
        event_id: str,
        severity: str,
        category: str,
        title: str,
        actions: tuple[str, ...],
    ) -> GovernanceIncident:
        incident = GovernanceIncident(
            incident_id=_identifier("INC"),
            created_at=_now(),
            model_id=model_id,
            event_id=event_id,
            severity=severity,
            category=category,
            status="open",
            title=title,
            response_actions=actions,
        )
        self.incidents[incident.incident_id] = incident
        self.audit_log.append(
            "governance.incident_opened", incident.incident_id, incident.as_dict()
        )
        return incident

    def record_monitoring_event(
        self, model_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        model = self.models.get(model_id)
        if model is None:
            raise ValueError("Unknown deployed AI model.")
        if not model.monitoring_enabled:
            raise ValueError("Production monitoring is not enabled for this model.")
        metric = str(payload.get("metric", "")).strip()
        if metric not in {"drift_score", "bias_gap", "error_rate", "groundedness"}:
            raise ValueError("Unknown production monitoring metric.")
        try:
            value = float(payload.get("value"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Monitoring value must be numeric.") from exc
        if value < 0:
            raise ValueError("Monitoring value cannot be negative.")

        thresholds = {
            "drift_score": (0.15, "above"),
            "bias_gap": (0.08, "above"),
            "error_rate": (0.03, "above"),
            "groundedness": (0.80, "below"),
        }
        threshold, direction = thresholds[metric]
        breached = value > threshold if direction == "above" else value < threshold
        before_metrics = dict(model.metrics)
        previous = model.metrics.get(metric)
        model.metrics[metric] = value
        after_metrics = dict(model.metrics)
        monitoring_event_id = _identifier("MON")
        monitoring_event = {
            "monitoring_event_id": monitoring_event_id,
            "created_at": _now(),
            "model_id": model_id,
            "metric": metric,
            "previous_value": previous,
            "observed_value": value,
            "threshold": threshold,
            "threshold_direction": direction,
            "breached": breached,
        }
        self.monitoring_events[monitoring_event_id] = monitoring_event
        self.audit_log.append(
            "governance.monitoring_evaluated", monitoring_event_id, monitoring_event
        )

        incident: GovernanceIncident | None = None
        finding: Finding | None = None
        action = "continue"
        if breached:
            model.status = "guarded"
            action = "route_to_fallback_and_require_validation"
            incident = self._create_incident(
                model_id=model_id,
                event_id=monitoring_event_id,
                severity="high",
                category="model_monitoring",
                title=f"Production {metric.replace('_', ' ')} threshold breached",
                actions=(
                    "Guarded the deployed model",
                    "Routed eligible traffic to the approved fallback",
                    "Opened independent validation and owner review",
                ),
            )
            finding = self._new_finding(
                model_id=model_id,
                source="production_monitoring",
                severity="high",
                title=f"Production {metric.replace('_', ' ')} outside policy threshold",
                description=(
                    f"Observed {value:g}; policy threshold is {direction} {threshold:g}."
                ),
                policy_id="MON-001",
                mappings=(
                    "EU AI Act Arts. 12 and 15",
                    "DORA Art. 11",
                    "NIST AI RMF MANAGE",
                ),
                required_action="Validate the model and approve recovery before full traffic resumes.",
                control_action="guard_and_route",
                evidence_ref=monitoring_event_id,
            )

        return {
            "monitoring_event": monitoring_event,
            "action": action,
            "containment_status": "guarded_and_routed" if breached else "within_policy",
            "before_metrics": before_metrics,
            "after_metrics": after_metrics,
            "policy_breach": "MON-001" if breached else None,
            "regulatory_obligations_at_risk": (
                [
                    "EU AI Act Arts. 12 and 15",
                    "DORA Art. 11",
                    "NIST AI RMF MANAGE",
                ]
                if breached
                else []
            ),
            "legal_violation_confirmed": False,
            "owner": model.owner,
            "evidence_id": monitoring_event_id,
            "model": model.as_dict(),
            "incident": incident.as_dict() if incident else None,
            "finding": finding.as_dict() if finding else None,
        }

    def observe_model_version(
        self, model_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Compare a live provider/runtime version with its approved passport."""

        model = self.models.get(model_id)
        if model is None:
            raise ValueError("Unknown deployed AI model.")
        observed_version = str(payload.get("observed_version", "")).strip()
        if not observed_version:
            raise ValueError("An observed model version is required.")
        previous_version = model.version
        model.version = observed_version
        event_id = _identifier("VER")
        matched = observed_version == model.approved_version
        event = {
            "version_event_id": event_id,
            "created_at": _now(),
            "model_id": model_id,
            "previous_version": previous_version,
            "observed_version": observed_version,
            "approved_version": model.approved_version,
            "matched": matched,
        }
        self.version_events[event_id] = event
        self.audit_log.append("governance.version_observed", event_id, event)

        incident: GovernanceIncident | None = None
        finding: Finding | None = None
        if matched:
            action = "continue"
            containment_status = "approved_version_running"
        else:
            model.status = "guarded"
            action = "block_write_actions_and_route_to_approved_version"
            containment_status = "version_mismatch_contained"
            incident = self._create_incident(
                model_id=model_id,
                event_id=event_id,
                severity="high",
                category="model_change_management",
                title="Unapproved production model version detected",
                actions=(
                    "Blocked write-capable use of the observed version",
                    "Routed eligible traffic to the last approved version",
                    "Opened change-impact assessment and revalidation",
                ),
            )
            finding = self._new_finding(
                model_id=model_id,
                source="deployment_discovery",
                severity="high",
                title="Production version does not match approved model passport",
                description=(
                    f"Observed {observed_version}; approved version is "
                    f"{model.approved_version}."
                ),
                policy_id="USE-001",
                mappings=(
                    "EU AI Act Arts. 9 and 15",
                    "DORA change-management controls",
                    "NIST AI RMF MAP and MANAGE",
                ),
                required_action="Complete change-impact review and revalidation before release.",
                control_action="guard_and_route",
                evidence_ref=event_id,
            )
        return {
            "version_event": event,
            "action": action,
            "containment_status": containment_status,
            "policy_breach": None if matched else "USE-001",
            "regulatory_obligations_at_risk": (
                []
                if matched
                else [
                    "EU AI Act Arts. 9 and 15",
                    "DORA change-management controls",
                    "NIST AI RMF MAP and MANAGE",
                ]
            ),
            "legal_violation_confirmed": False,
            "owner": model.owner,
            "evidence_id": event_id,
            "model": model.as_dict(),
            "incident": incident.as_dict() if incident else None,
            "finding": finding.as_dict() if finding else None,
        }

    def resolve_finding(self, finding_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        finding = self.findings.get(finding_id)
        if finding is None:
            raise ValueError("Unknown governance finding.")
        rationale = str(payload.get("rationale", "")).strip()
        owner = str(payload.get("owner", "")).strip()
        if not rationale or not owner:
            raise ValueError("A remediation owner and rationale are required.")
        finding.status = "remediated"
        self.audit_log.append(
            "governance.finding_remediated",
            finding.finding_id,
            {"owner": owner, "rationale": rationale, "resolved_at": _now()},
        )
        return finding.as_dict()

    def evidence(self, object_id: str) -> dict[str, Any]:
        subject: dict[str, Any] | None = None
        if object_id in self.events:
            subject = self.events[object_id].as_dict()
        elif object_id in self.monitoring_events:
            subject = self.monitoring_events[object_id]
        elif object_id in self.version_events:
            subject = self.version_events[object_id]
        elif object_id in self.assessments:
            subject = self.assessments[object_id].as_dict()
        elif object_id in self.findings:
            subject = self.findings[object_id].as_dict()
        elif object_id in self.incidents:
            subject = self.incidents[object_id].as_dict()
        if subject is None:
            raise ValueError("Unknown governance evidence object.")

        related_ids = {object_id}
        if "event_id" in subject:
            related_ids.add(str(subject["event_id"]))
        if "evidence_ref" in subject:
            related_ids.add(str(subject["evidence_ref"]))
        for finding in self.findings.values():
            if finding.evidence_ref in related_ids:
                related_ids.add(finding.finding_id)
        for incident in self.incidents.values():
            if incident.event_id in related_ids:
                related_ids.add(incident.incident_id)

        records = [
            record
            for record in self.audit_log.records()
            if record["action_id"] in related_ids
            or str(record["payload"].get("event_id", "")) in related_ids
            or str(record["payload"].get("evidence_ref", "")) in related_ids
        ]
        try:
            audit_valid = self.audit_log.verify()
        except AuditIntegrityError:
            audit_valid = False
        return {
            "schema": "styrai.ai-governance-evidence.v1",
            "generated_at": _now(),
            "subject_id": object_id,
            "subject": subject,
            "related_findings": [
                item.as_dict()
                for item in self.findings.values()
                if item.finding_id in related_ids or item.evidence_ref in related_ids
            ],
            "related_incidents": [
                item.as_dict()
                for item in self.incidents.values()
                if item.incident_id in related_ids or item.event_id in related_ids
            ],
            "audit_records": records,
            "audit_chain_valid": audit_valid,
            "raw_prompts_retained": False,
            "disclaimer": "Synthetic demonstration evidence; not legal certification.",
        }

    def state(self) -> dict[str, Any]:
        models = list(self.models.values())
        latest_by_model: dict[str, Assessment] = {}
        for assessment in self.assessments.values():
            latest_by_model[assessment.model_id] = assessment
        open_findings = [item for item in self.findings.values() if item.status == "open"]
        try:
            audit_valid = self.audit_log.verify()
        except AuditIntegrityError:
            audit_valid = False
        return {
            "generated_at": _now(),
            "mode": "synthetic_local_control_plane",
            "metrics": {
                "deployed_models": sum(
                    item.environment == "production" for item in models
                ),
                "registered_models": sum(item.registered for item in models),
                "high_impact_models": sum(
                    item.risk_class == "high_impact" for item in models
                ),
                "models_guarded_or_blocked": sum(
                    item.status in {"guarded", "blocked"} for item in models
                ),
                "open_findings": len(open_findings),
                "critical_findings": sum(
                    item.severity == "critical" for item in open_findings
                ),
                "runtime_events": len(self.events),
                "prevented_transmissions": sum(
                    item.transmission_prevented for item in self.events.values()
                ),
                "open_incidents": sum(
                    item.status == "open" for item in self.incidents.values()
                ),
            },
            "models": [item.as_dict() for item in models],
            "assessments": [
                item.as_dict()
                for item in sorted(
                    latest_by_model.values(),
                    key=lambda value: value.created_at,
                    reverse=True,
                )
            ],
            "findings": [
                item.as_dict()
                for item in sorted(
                    self.findings.values(),
                    key=lambda value: value.created_at,
                    reverse=True,
                )
            ],
            "runtime_events": [
                item.as_dict()
                for item in reversed(list(self.events.values())[-50:])
            ],
            "monitoring_events": list(
                reversed(list(self.monitoring_events.values())[-50:])
            ),
            "version_events": list(
                reversed(list(self.version_events.values())[-50:])
            ),
            "incidents": [
                item.as_dict()
                for item in sorted(
                    self.incidents.values(),
                    key=lambda value: value.created_at,
                    reverse=True,
                )
            ],
            "control_catalog": [
                {**item, "mappings": list(item["mappings"])}
                for item in CONTROL_CATALOG
            ],
            "enforcement": {
                "inspection_point": "before_provider_boundary",
                "decisions": ["allow", "redact", "block", "route"],
                "unknown_model_policy": "fail_closed",
                "secrets_policy": "block_everywhere",
                "restricted_external_policy": "route_to_private_or_block",
                "raw_prompts_retained": False,
            },
            "audit": {
                "valid": audit_valid,
                "record_count": len(self.audit_log.records()),
            },
        }
