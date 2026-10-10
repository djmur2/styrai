"""Full-governance operating demonstration for StyrAI.

The module deliberately uses deterministic, local simulations. It demonstrates
the governance lifecycle and evidence model without connecting to real models,
customer data, messaging systems, or financial or healthcare infrastructure.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from .audit import AuditIntegrityError, HashChainedAuditLog


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def date_offset(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).date().isoformat()


SENSITIVITY = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


@dataclass
class ModelHealth:
    status: str
    calls_24h: int
    blocked_24h: int
    error_rate: float
    groundedness: float
    drift_score: float
    p95_latency_ms: int
    cost_24h_nok: float
    history: list[float] = field(default_factory=list)


@dataclass
class AISystem:
    asset_id: str
    name: str
    asset_type: str
    provider: str
    model: str
    version: str
    approved_version: str
    environment: str
    owner: str
    business_unit: str
    intended_use: str
    risk_tier: str
    status: str
    region: str
    external_provider: bool
    contract_status: str
    zero_retention: bool
    data_classes: tuple[str, ...]
    tools: tuple[str, ...]
    last_review: str
    next_review: str
    monitoring_enabled: bool
    health: ModelHealth

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["data_classes"] = list(self.data_classes)
        payload["tools"] = list(self.tools)
        return payload


@dataclass
class RuntimeEvent:
    event_id: str
    timestamp: str
    asset_id: str
    asset_name: str
    actor: str
    declared_classification: str
    effective_classification: str
    detected_data_types: tuple[str, ...]
    destination: str
    decision: str
    reason: str
    controls_applied: tuple[str, ...]
    redaction_count: int
    redacted_preview: str
    prompt_hash: str
    latency_ms: int
    estimated_tokens: int
    estimated_cost_nok: float
    outcome: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["detected_data_types"] = list(self.detected_data_types)
        payload["controls_applied"] = list(self.controls_applied)
        return payload


@dataclass
class Control:
    control_id: str
    title: str
    domain: str
    objective: str
    mode: str
    automated: bool
    status: str
    coverage: int
    owner: str
    frameworks: tuple[str, ...]
    evidence_count: int
    last_tested: str
    next_test: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["frameworks"] = list(self.frameworks)
        return payload


@dataclass
class AutomationRule:
    rule_id: str
    name: str
    description: str
    trigger: str
    actions: tuple[str, ...]
    enabled: bool
    mode: str
    runs: int
    last_run: str | None
    last_result: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["actions"] = list(self.actions)
        return payload


@dataclass
class AutomationRun:
    run_id: str
    timestamp: str
    rule_id: str
    rule_name: str
    trigger: str
    result: str
    actions_taken: tuple[str, ...]
    related_object: str | None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["actions_taken"] = list(self.actions_taken)
        return payload


@dataclass
class Incident:
    incident_id: str
    created_at: str
    severity: str
    title: str
    category: str
    status: str
    asset_id: str | None
    summary: str
    automated_actions: tuple[str, ...]
    owner: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["automated_actions"] = list(self.automated_actions)
        return payload


@dataclass
class EvidencePack:
    pack_id: str
    generated_at: str
    name: str
    scope: str
    frameworks: tuple[str, ...]
    control_count: int
    event_count: int
    incident_count: int
    audit_chain_valid: bool
    audit_tip: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["frameworks"] = list(self.frameworks)
        return payload


@dataclass(frozen=True)
class SensitivePattern:
    name: str
    classification: str
    expression: re.Pattern[str]
    replacement: str


PATTERNS = (
    SensitivePattern(
        "api_secret",
        "restricted",
        re.compile(r"(?i)\b(api[_ -]?key|password|secret)\s*[:=]\s*[^\s,;]+"),
        "[REDACTED SECRET]",
    ),
    SensitivePattern(
        "norwegian_national_id",
        "restricted",
        re.compile(r"(?<!\d)\d{11}(?!\d)"),
        "[REDACTED NATIONAL ID]",
    ),
    SensitivePattern(
        "healthcare_patient_identifier",
        "restricted",
        re.compile(
            r"(?i)\b(?:(?:mrn|patient[_ -]?id)\s*[:#=]\s*"
            r"[A-Z0-9][A-Z0-9-]{3,24}|(?:MRN|PAT)-DEMO-\d{3,8})\b"
        ),
        "[REDACTED PATIENT ID]",
    ),
    SensitivePattern(
        "phone_number",
        "confidential",
        re.compile(
            r"(?i)\b(?:phone|mobile|telephone|tel)\s*[:=]?\s*"
            r"\+?\d(?:[\d .()-]{5,}\d)"
        ),
        "[REDACTED PHONE]",
    ),
    SensitivePattern(
        "iban_or_account",
        "confidential",
        re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9 ]{10,30}\b"),
        "[REDACTED ACCOUNT]",
    ),
    SensitivePattern(
        "email_address",
        "confidential",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[REDACTED EMAIL]",
    ),
    SensitivePattern(
        "confidential_marker",
        "confidential",
        re.compile(r"(?i)\b(confidential|strictly private|customer secret)\b"),
        "[CONFIDENTIAL]",
    ),
)


class GovernancePlatform:
    """Stateful demonstration of continuous AI governance operations."""

    def __init__(self, audit_log: HashChainedAuditLog) -> None:
        self.audit_log = audit_log
        self.assets: dict[str, AISystem] = {}
        self.controls: dict[str, Control] = {}
        self.automations: dict[str, AutomationRule] = {}
        self.automation_runs: list[AutomationRun] = []
        self.events: list[RuntimeEvent] = []
        self.incidents: dict[str, Incident] = {}
        self.evidence_packs: dict[str, EvidencePack] = {}
        self._seed()

    def _seed(self) -> None:
        self.assets = {asset.asset_id: asset for asset in self._seed_assets()}
        self.controls = {
            control.control_id: control for control in self._seed_controls()
        }
        self.automations = {
            rule.rule_id: rule for rule in self._seed_automations()
        }
        self._create_incident(
            severity="high",
            title="Unapproved public AI service discovered",
            category="shadow_ai",
            asset_id="shadow-public-ai",
            summary=(
                "Network discovery identified an unregistered public AI service "
                "used outside the approved model gateway."
            ),
            automated_actions=(
                "Blocked the destination at the model gateway",
                "Opened an owner-attestation task",
                "Preserved discovery evidence",
            ),
            owner="AI Governance Lead",
            audit=False,
        )
        self._seed_runtime_events()

    @staticmethod
    def _seed_assets() -> tuple[AISystem, ...]:
        return (
            AISystem(
                asset_id="agent-client-service",
                name="Client Service Copilot",
                asset_type="AI agent",
                provider="Approved EU model gateway",
                model="Enterprise language model",
                version="2026-08",
                approved_version="2026-08",
                environment="production",
                owner="Head of Client Service",
                business_unit="Retail Banking",
                intended_use="Draft and retrieve customer-service information",
                risk_tier="medium",
                status="approved",
                region="EU/Norway",
                external_provider=True,
                contract_status="approved",
                zero_retention=True,
                data_classes=("public", "internal", "confidential"),
                tools=("knowledge_search", "draft_response"),
                last_review=date_offset(-18),
                next_review=date_offset(72),
                monitoring_enabled=True,
                health=ModelHealth(
                    status="healthy",
                    calls_24h=18_420,
                    blocked_24h=37,
                    error_rate=0.012,
                    groundedness=0.93,
                    drift_score=0.04,
                    p95_latency_ms=820,
                    cost_24h_nok=1_842.0,
                    history=[0.91, 0.92, 0.94, 0.93, 0.92, 0.94, 0.93],
                ),
            ),
            AISystem(
                asset_id="model-credit-risk",
                name="Retail Credit Risk Model",
                asset_type="Predictive model",
                provider="Customer hosted",
                model="Gradient boosting ensemble",
                version="12.4",
                approved_version="12.4",
                environment="production",
                owner="Head of Credit Risk Models",
                business_unit="Risk",
                intended_use="Analyst decision support for retail credit risk",
                risk_tier="high",
                status="approved",
                region="Norway",
                external_provider=False,
                contract_status="internal",
                zero_retention=True,
                data_classes=("internal", "confidential", "restricted"),
                tools=("score", "explain"),
                last_review=date_offset(-42),
                next_review=date_offset(48),
                monitoring_enabled=True,
                health=ModelHealth(
                    status="healthy",
                    calls_24h=7_840,
                    blocked_24h=0,
                    error_rate=0.003,
                    groundedness=0.96,
                    drift_score=0.07,
                    p95_latency_ms=94,
                    cost_24h_nok=420.0,
                    history=[0.95, 0.96, 0.96, 0.95, 0.96, 0.96, 0.96],
                ),
            ),
            AISystem(
                asset_id="agent-payment-ops",
                name="Payment Operations Agent",
                asset_type="Action agent",
                provider="Customer hosted",
                model="Operations reasoning model",
                version="2026-08-15",
                approved_version="2026-08-15",
                environment="production",
                owner="Head of Payment Operations",
                business_unit="Operations",
                intended_use="Prepare payment batches; release requires dual approval",
                risk_tier="high",
                status="approved",
                region="Norway",
                external_provider=False,
                contract_status="internal",
                zero_retention=True,
                data_classes=("internal", "confidential", "restricted"),
                tools=("prepare_batch", "propose_release"),
                last_review=date_offset(-8),
                next_review=date_offset(82),
                monitoring_enabled=True,
                health=ModelHealth(
                    status="healthy",
                    calls_24h=2_312,
                    blocked_24h=12,
                    error_rate=0.006,
                    groundedness=0.97,
                    drift_score=0.02,
                    p95_latency_ms=410,
                    cost_24h_nok=590.0,
                    history=[0.96, 0.97, 0.97, 0.96, 0.98, 0.97, 0.97],
                ),
            ),
            AISystem(
                asset_id="agent-healthcare-visit-summary",
                name="Healthcare Visit Summary Copilot",
                asset_type="AI agent",
                provider="Customer-hosted healthcare AI environment",
                model="Clinical summary model",
                version="2026-08-2",
                approved_version="2026-08-2",
                environment="production",
                owner="Director of Clinical Informatics",
                business_unit="Outpatient Care",
                intended_use=(
                    "Draft source-grounded visit summaries for clinician approval"
                ),
                risk_tier="high",
                status="approved",
                region="Norway",
                external_provider=False,
                contract_status="internal",
                zero_retention=True,
                data_classes=("internal", "confidential", "restricted"),
                tools=("draft_summary", "propose_publish"),
                last_review=date_offset(-12),
                next_review=date_offset(78),
                monitoring_enabled=True,
                health=ModelHealth(
                    status="healthy",
                    calls_24h=1_286,
                    blocked_24h=14,
                    error_rate=0.006,
                    groundedness=0.985,
                    drift_score=0.03,
                    p95_latency_ms=690,
                    cost_24h_nok=248.0,
                    history=[0.98, 0.99, 0.98, 0.99, 0.99, 0.98, 0.99],
                ),
            ),
            AISystem(
                asset_id="model-claims-summary",
                name="Claims Document Summariser",
                asset_type="Generative model",
                provider="Approved EU model gateway",
                model="Enterprise language model",
                version="2026-07",
                approved_version="2026-07",
                environment="production",
                owner="Claims Technology Owner",
                business_unit="Insurance",
                intended_use="Summarise claims documents for human review",
                risk_tier="medium",
                status="approved",
                region="EU",
                external_provider=True,
                contract_status="approved",
                zero_retention=True,
                data_classes=("internal", "confidential"),
                tools=("summarise",),
                last_review=date_offset(-61),
                next_review=date_offset(29),
                monitoring_enabled=True,
                health=ModelHealth(
                    status="watch",
                    calls_24h=4_991,
                    blocked_24h=9,
                    error_rate=0.021,
                    groundedness=0.84,
                    drift_score=0.11,
                    p95_latency_ms=1_340,
                    cost_24h_nok=1_130.0,
                    history=[0.91, 0.90, 0.89, 0.88, 0.87, 0.85, 0.84],
                ),
            ),
            AISystem(
                asset_id="shadow-public-ai",
                name="Unapproved Public AI Assistant",
                asset_type="Shadow AI",
                provider="Public consumer service",
                model="Unknown",
                version="unverified",
                approved_version="none",
                environment="shadow",
                owner="Unassigned",
                business_unit="Unknown",
                intended_use="Unapproved",
                risk_tier="critical",
                status="blocked",
                region="Unknown",
                external_provider=True,
                contract_status="none",
                zero_retention=False,
                data_classes=(),
                tools=(),
                last_review="Never",
                next_review="Immediate",
                monitoring_enabled=False,
                health=ModelHealth(
                    status="blocked",
                    calls_24h=23,
                    blocked_24h=23,
                    error_rate=0.0,
                    groundedness=0.0,
                    drift_score=0.0,
                    p95_latency_ms=0,
                    cost_24h_nok=0.0,
                    history=[0, 0, 0, 0, 0, 0, 0],
                ),
            ),
        )

    @staticmethod
    def _seed_controls() -> tuple[Control, ...]:
        today = date_offset(0)
        return (
            Control("AI-INV-01", "Complete AI system inventory", "Inventory", "Every model, agent, provider and owner is registered", "preventive", True, "effective", 96, "AI Governance Lead", ("EU AI Act", "ISO 42001", "DORA"), 142, today, date_offset(1)),
            Control("MODEL-USE-02", "Approved model and intended-use passport", "Model governance", "Only approved versions operate within approved purposes", "preventive", True, "effective", 92, "Model Risk", ("EU AI Act", "NIST AI RMF", "ISO 42001"), 318, today, date_offset(1)),
            Control("DATA-OUT-01", "Outbound sensitive-data policy", "Data protection", "Sensitive information cannot reach an unapproved AI destination", "preventive", True, "effective", 89, "Data Protection Officer", ("GDPR", "DORA", "ISO 42001"), 1_842, today, date_offset(1)),
            Control("HUMAN-01", "Human oversight and separation of duties", "Human oversight", "Consequential agent actions require accountable human review", "preventive", True, "effective", 84, "Operational Risk", ("EU AI Act", "EBA/EIOPA/ESMA"), 427, today, date_offset(7)),
            Control("MON-01", "Production quality and drift thresholds", "Model monitoring", "Quality, error, drift and latency breaches create action", "detective", True, "watch", 78, "Model Monitoring", ("EU AI Act", "NIST AI RMF", "ISO 42001"), 664, today, date_offset(1)),
            Control("TP-01", "AI provider and concentration-risk review", "Third-party risk", "External providers have approved terms, regions and exit plans", "preventive", False, "improvement", 67, "Third-Party Risk", ("DORA", "EBA"), 38, date_offset(-14), date_offset(16)),
            Control("INC-01", "Automated AI incident response", "Incident management", "Policy and monitoring breaches are contained and evidenced", "corrective", True, "effective", 91, "Security Operations", ("DORA", "NIST AI RMF"), 203, today, date_offset(1)),
            Control("EVID-01", "Reconstructable governance evidence", "Evidence", "Decisions retain identity, model, policy, approval and outcome context", "detective", True, "effective", 94, "AI Governance Lead", ("EU AI Act", "ISO 42001", "DORA", "GDPR"), 3_912, today, date_offset(1)),
        )

    @staticmethod
    def _seed_automations() -> tuple[AutomationRule, ...]:
        return (
            AutomationRule("AUTO-SHADOW", "Shadow AI discovery", "Find unregistered model destinations and open ownership tasks", "Every 15 minutes", ("Block unapproved destination", "Create incident", "Request owner attestation"), True, "enforce", 2_184, date_offset(0), "1 blocked destination"),
            AutomationRule("AUTO-DLP", "Confidential-data interception", "Classify outbound AI inputs before they leave the trust boundary", "Every model call", ("Block or redact payload", "Record metadata-only evidence", "Escalate restricted data"), True, "enforce", 48_921, date_offset(0), "37 sensitive calls controlled"),
            AutomationRule("AUTO-DRIFT", "Model health response", "Respond when quality, error, latency or drift crosses threshold", "Continuous metrics", ("Route to approved fallback", "Open validation task", "Notify model owner"), True, "enforce", 762, date_offset(0), "No new critical breach"),
            AutomationRule("AUTO-VERSION", "Model version change gate", "Prevent silent provider or model-version changes", "On version discovery", ("Pause write-capable actions", "Require revalidation", "Generate change-impact report"), True, "enforce", 91, date_offset(-1), "All versions matched"),
            AutomationRule("AUTO-PASSPORT", "Passport expiry review", "Suspend uses whose ownership, purpose or approval has expired", "Daily 06:00", ("Create owner task", "Move to review-required", "Block after grace period"), True, "enforce", 341, date_offset(0), "2 reviews due in 30 days"),
            AutomationRule("AUTO-EVIDENCE", "Evidence pack generation", "Build a signed governance evidence bundle for review", "Weekly and on demand", ("Verify audit chain", "Collect control evidence", "Produce framework crosswalk"), True, "assist", 42, date_offset(-4), "Last pack verified"),
        )

    def _seed_runtime_events(self) -> None:
        seed = (
            ("agent-client-service", "advisor-1042", "internal", "allow", "Approved internal knowledge retrieval", ("MODEL-USE-02",), "How do I explain our standard mortgage process?"),
            ("agent-client-service", "advisor-2091", "confidential", "allow_with_redaction", "Personal identifiers were removed before the approved model gateway", ("DATA-OUT-01", "MODEL-USE-02"), "Please draft a reply to [REDACTED EMAIL] about their account."),
            ("agent-payment-ops", "payments-operator-19", "restricted", "pending_approval", "Material payment proposal requires two-person approval", ("HUMAN-01", "MODEL-USE-02"), "Payment batch metadata retained customer-side."),
            ("agent-healthcare-visit-summary", "care-coordinator-demo", "restricted", "allow_with_redaction", "Direct patient identifiers were removed and publication remains subject to clinician approval", ("DATA-OUT-01", "MODEL-USE-02", "HUMAN-01"), "Visit summary for [REDACTED PATIENT ID] is pending clinician approval."),
            ("shadow-public-ai", "unknown-user", "confidential", "blocked", "Unapproved public destination", ("AI-INV-01", "DATA-OUT-01"), "[CONFIDENTIAL] content blocked before transmission."),
        )
        for index, (asset_id, actor, classification, decision, reason, controls, preview) in enumerate(seed):
            asset = self.assets[asset_id]
            event = RuntimeEvent(
                event_id=f"seed-event-{index + 1}",
                timestamp=(datetime.now(UTC) - timedelta(minutes=4 - index)).isoformat(timespec="milliseconds"),
                asset_id=asset_id,
                asset_name=asset.name,
                actor=actor,
                declared_classification=classification,
                effective_classification=classification,
                detected_data_types=(),
                destination=asset.provider,
                decision=decision,
                reason=reason,
                controls_applied=controls,
                redaction_count=1 if decision == "allow_with_redaction" else 0,
                redacted_preview=preview,
                prompt_hash=hashlib.sha256(preview.encode()).hexdigest(),
                latency_ms=440 + index * 77,
                estimated_tokens=90 + index * 31,
                estimated_cost_nok=0.21 + index * 0.08,
                outcome="controlled",
            )
            self.events.append(event)

    def _create_incident(
        self,
        *,
        severity: str,
        title: str,
        category: str,
        asset_id: str | None,
        summary: str,
        automated_actions: tuple[str, ...],
        owner: str,
        audit: bool = True,
    ) -> Incident:
        incident = Incident(
            incident_id="INC-" + uuid4().hex[:8].upper(),
            created_at=now_iso(),
            severity=severity,
            title=title,
            category=category,
            status="open",
            asset_id=asset_id,
            summary=summary,
            automated_actions=automated_actions,
            owner=owner,
        )
        self.incidents[incident.incident_id] = incident
        if audit:
            self.audit_log.append(
                "incident.created", incident.incident_id, incident.as_dict()
            )
        return incident

    @staticmethod
    def _detect_sensitive(prompt: str) -> tuple[str, tuple[str, ...], int, str]:
        effective = "public"
        names: list[str] = []
        redacted = prompt
        count = 0
        for pattern in PATTERNS:
            matches = list(pattern.expression.finditer(redacted))
            if matches:
                names.append(pattern.name)
                count += len(matches)
                if SENSITIVITY[pattern.classification] > SENSITIVITY[effective]:
                    effective = pattern.classification
                redacted = pattern.expression.sub(pattern.replacement, redacted)
        redacted = redacted.strip().replace("\n", " ")[:260]
        return effective, tuple(names), count, redacted

    def simulate_model_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(payload.get("asset_id", ""))
        asset = self.assets.get(asset_id)
        if asset is None:
            raise ValueError("Unknown AI system.")
        prompt = str(payload.get("prompt", ""))
        if not prompt.strip():
            raise ValueError("A demonstration input is required.")
        if len(prompt) > 10_000:
            raise ValueError("Demonstration input is too long.")
        actor = str(payload.get("actor", "demo-user")).strip() or "demo-user"
        declared = str(payload.get("classification", "internal"))
        if declared not in SENSITIVITY:
            raise ValueError("Unknown data classification.")

        detected_class, data_types, redaction_count, redacted = self._detect_sensitive(prompt)
        effective = max((declared, detected_class), key=lambda item: SENSITIVITY[item])
        controls = ["AI-INV-01", "MODEL-USE-02", "DATA-OUT-01"]

        if asset.status not in {"approved", "guarded"}:
            decision = "blocked"
            reason = "The AI system or exact model version is not approved for production use."
        elif "api_secret" in data_types:
            decision = "blocked"
            reason = "Secrets are prohibited from all model inputs."
        elif effective == "restricted" and asset.external_provider:
            decision = "blocked"
            reason = "Restricted information cannot leave the customer trust boundary."
        elif effective == "restricted":
            decision = "pending_approval"
            reason = "Restricted internal processing requires recorded human approval."
            controls.append("HUMAN-01")
        elif effective == "confidential" and asset.external_provider and (
            asset.contract_status != "approved" or not asset.zero_retention
        ):
            decision = "blocked"
            reason = "The destination lacks approved contractual and retention controls."
        elif effective == "confidential" and asset.external_provider:
            decision = "allow_with_redaction"
            reason = "Sensitive fields were removed before the approved zero-retention gateway."
        elif effective not in asset.data_classes:
            decision = "blocked"
            reason = "The model passport does not permit this data classification."
        else:
            decision = "allowed"
            reason = "The model passport, destination and data policy permit this use."

        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        event = RuntimeEvent(
            event_id="EVT-" + uuid4().hex[:10].upper(),
            timestamp=now_iso(),
            asset_id=asset.asset_id,
            asset_name=asset.name,
            actor=actor,
            declared_classification=declared,
            effective_classification=effective,
            detected_data_types=data_types,
            destination=asset.provider,
            decision=decision,
            reason=reason,
            controls_applied=tuple(dict.fromkeys(controls)),
            redaction_count=redaction_count,
            redacted_preview=redacted,
            prompt_hash=prompt_hash,
            latency_ms=520 + (len(prompt) % 431),
            estimated_tokens=max(12, len(prompt) // 4),
            estimated_cost_nok=round(max(12, len(prompt) // 4) * 0.0027, 2),
            outcome="prevented" if decision == "blocked" else "controlled",
        )
        self.events.append(event)
        asset.health.calls_24h += 1
        if decision == "blocked":
            asset.health.blocked_24h += 1
        self.audit_log.append(
            "runtime.call_evaluated",
            event.event_id,
            {
                key: value
                for key, value in event.as_dict().items()
                if key != "redacted_preview"
            },
        )

        incident: Incident | None = None
        automation_run: AutomationRun | None = None
        if decision == "blocked":
            severity = "critical" if effective == "restricted" else "high"
            incident = self._create_incident(
                severity=severity,
                title="Sensitive AI input blocked",
                category="data_protection",
                asset_id=asset.asset_id,
                summary=reason,
                automated_actions=(
                    "Prevented transmission",
                    "Recorded metadata-only evidence",
                    "Notified the data and model owners",
                ),
                owner="Data Protection Officer",
            )
            automation_run = self._record_automation_run(
                "AUTO-DLP",
                trigger=f"Runtime event {event.event_id}",
                result="Sensitive input contained",
                related_object=incident.incident_id,
            )

        return {
            "event": event.as_dict(),
            "incident": incident.as_dict() if incident else None,
            "automation_run": automation_run.as_dict() if automation_run else None,
            "raw_input_stored": False,
        }

    def simulate_health_breach(self, asset_id: str, breach: str) -> dict[str, Any]:
        asset = self.assets.get(asset_id)
        if asset is None:
            raise ValueError("Unknown AI system.")
        if not asset.monitoring_enabled:
            raise ValueError("Monitoring is not enabled for this system.")

        if breach == "quality":
            asset.health.groundedness = 0.68
            asset.health.error_rate = 0.047
            title = "Model quality threshold breached"
            summary = "Groundedness fell below 0.80 and the error rate exceeded 3%."
        elif breach == "drift":
            asset.health.drift_score = 0.27
            title = "Production model drift detected"
            summary = "Population drift exceeded the approved 0.15 threshold."
        elif breach == "latency":
            asset.health.p95_latency_ms = 3_240
            title = "Model latency threshold breached"
            summary = "P95 latency exceeded the 2,000 ms operating threshold."
        else:
            raise ValueError("Unknown health-breach scenario.")

        asset.health.status = "degraded"
        asset.status = "guarded"
        incident = self._create_incident(
            severity="high",
            title=title,
            category="model_monitoring",
            asset_id=asset.asset_id,
            summary=summary,
            automated_actions=(
                "Routed write-capable requests to the approved fallback",
                "Opened a model-validation task",
                "Notified the model owner and operational risk",
            ),
            owner="Model Monitoring",
        )
        run = self._record_automation_run(
            "AUTO-DRIFT",
            trigger=f"Health threshold on {asset.name}",
            result="Fallback and validation workflow activated",
            related_object=incident.incident_id,
        )
        self.audit_log.append(
            "model.health_breach",
            asset.asset_id,
            {
                "breach": breach,
                "health": asdict(asset.health),
                "incident_id": incident.incident_id,
            },
        )
        return {
            "asset": asset.as_dict(),
            "incident": incident.as_dict(),
            "automation_run": run.as_dict(),
        }

    def simulate_version_change(self, asset_id: str) -> dict[str, Any]:
        asset = self.assets.get(asset_id)
        if asset is None:
            raise ValueError("Unknown AI system.")
        previous = asset.version
        asset.version = f"{previous}-provider-update"
        asset.status = "review_required"
        asset.health.status = "paused"
        incident = self._create_incident(
            severity="high",
            title="Unapproved model-version change detected",
            category="model_change",
            asset_id=asset.asset_id,
            summary=(
                f"Runtime reported version {asset.version}; approved passport remains "
                f"{asset.approved_version}."
            ),
            automated_actions=(
                "Paused write-capable actions",
                "Retained the approved version as fallback",
                "Created revalidation and change-impact tasks",
            ),
            owner="Model Risk",
        )
        run = self._record_automation_run(
            "AUTO-VERSION",
            trigger=f"Version discovery on {asset.name}",
            result="Unapproved version contained",
            related_object=incident.incident_id,
        )
        self.audit_log.append(
            "model.version_change_detected",
            asset.asset_id,
            {
                "previous_version": previous,
                "observed_version": asset.version,
                "approved_version": asset.approved_version,
                "incident_id": incident.incident_id,
            },
        )
        return {
            "asset": asset.as_dict(),
            "incident": incident.as_dict(),
            "automation_run": run.as_dict(),
        }

    def _record_automation_run(
        self,
        rule_id: str,
        *,
        trigger: str,
        result: str,
        related_object: str | None,
    ) -> AutomationRun:
        rule = self.automations[rule_id]
        if not rule.enabled:
            raise ValueError("Automation is disabled.")
        run = AutomationRun(
            run_id="RUN-" + uuid4().hex[:8].upper(),
            timestamp=now_iso(),
            rule_id=rule_id,
            rule_name=rule.name,
            trigger=trigger,
            result=result,
            actions_taken=rule.actions,
            related_object=related_object,
        )
        self.automation_runs.append(run)
        rule.runs += 1
        rule.last_run = run.timestamp
        rule.last_result = result
        self.audit_log.append("automation.completed", run.run_id, run.as_dict())
        return run

    def run_automation(self, rule_id: str) -> dict[str, Any]:
        rule = self.automations.get(rule_id)
        if rule is None:
            raise ValueError("Unknown automation.")
        related_object: str | None = None
        if rule_id == "AUTO-EVIDENCE":
            pack = self.generate_evidence_pack()
            related_object = pack.pack_id
            result = "Evidence pack generated and integrity verified"
        elif rule_id == "AUTO-SHADOW":
            result = "1 blocked shadow destination remains contained"
            related_object = "shadow-public-ai"
        elif rule_id == "AUTO-PASSPORT":
            due = [
                asset for asset in self.assets.values()
                if asset.next_review not in {"Immediate", "Never"}
                and asset.next_review <= date_offset(30)
            ]
            result = f"{len(due)} model passport reviews due within 30 days"
        elif rule_id == "AUTO-VERSION":
            mismatches = [
                asset for asset in self.assets.values()
                if asset.version != asset.approved_version and asset.status != "blocked"
            ]
            result = f"{len(mismatches)} unapproved version mismatches contained"
        elif rule_id == "AUTO-DRIFT":
            degraded = [
                asset for asset in self.assets.values()
                if asset.health.status in {"degraded", "paused"}
            ]
            result = f"{len(degraded)} degraded model deployments under active control"
        elif rule_id == "AUTO-DLP":
            result = "Outbound AI data policies tested successfully"
        else:
            result = "Automation completed"
        run = self._record_automation_run(
            rule_id,
            trigger="Manual demonstration run",
            result=result,
            related_object=related_object,
        )
        return {"automation": rule.as_dict(), "run": run.as_dict()}

    def generate_evidence_pack(self) -> EvidencePack:
        try:
            valid = self.audit_log.verify()
        except AuditIntegrityError:
            valid = False
        records = self.audit_log.records()
        tip = records[-1]["record_hash"] if records else self.audit_log.GENESIS_HASH
        pack = EvidencePack(
            pack_id="PACK-" + uuid4().hex[:8].upper(),
            generated_at=now_iso(),
            name="AI Governance Operations Evidence Pack",
            scope="Production AI inventory, runtime controls, monitoring and incidents",
            frameworks=("EU AI Act", "DORA", "GDPR", "ISO 42001", "NIST AI RMF"),
            control_count=len(self.controls),
            event_count=len(self.events),
            incident_count=len(self.incidents),
            audit_chain_valid=valid,
            audit_tip=tip,
            status="verified" if valid else "integrity_review_required",
        )
        self.evidence_packs[pack.pack_id] = pack
        self.audit_log.append("evidence.pack_generated", pack.pack_id, pack.as_dict())
        return pack

    def resolve_incident(self, incident_id: str) -> dict[str, Any]:
        incident = self.incidents.get(incident_id)
        if incident is None:
            raise ValueError("Unknown incident.")
        incident.status = "resolved"
        self.audit_log.append(
            "incident.resolved",
            incident.incident_id,
            {"owner": incident.owner, "resolved_at": now_iso()},
        )
        return incident.as_dict()

    def evidence_pack(self, pack_id: str) -> dict[str, Any]:
        pack = self.evidence_packs.get(pack_id)
        if pack is None:
            raise ValueError("Unknown evidence pack.")
        return {
            "schema": "styrai.governance-evidence.v1",
            "pack": pack.as_dict(),
            "controls": [control.as_dict() for control in self.controls.values()],
            "incidents": [incident.as_dict() for incident in self.incidents.values()],
            "runtime_events": [event.as_dict() for event in self.events[-25:]],
            "automation_runs": [run.as_dict() for run in self.automation_runs[-25:]],
            "audit_records": list(self.audit_log.records()[-100:]),
            "audit_chain_valid": self.audit_log.verify(),
            "data_statement": (
                "Governance evidence contains approved metadata, hashes and "
                "redacted fields; raw model input is not retained."
            ),
            "disclaimer": "Demonstration evidence; not a compliance certification.",
        }

    def state(self) -> dict[str, Any]:
        assets = list(self.assets.values())
        production = [asset for asset in assets if asset.environment == "production"]
        monitored = [asset for asset in production if asset.monitoring_enabled]
        open_incidents = [
            incident for incident in self.incidents.values() if incident.status == "open"
        ]
        blocked_events = [event for event in self.events if event.decision == "blocked"]
        coverage = round(
            sum(control.coverage for control in self.controls.values())
            / max(1, len(self.controls))
        )
        external = [asset for asset in assets if asset.external_provider]
        spend = round(sum(asset.health.cost_24h_nok for asset in production), 2)
        calls = sum(asset.health.calls_24h for asset in production)
        try:
            audit_valid = self.audit_log.verify()
        except AuditIntegrityError:
            audit_valid = False

        return {
            "generated_at": now_iso(),
            "metrics": {
                "ai_systems": len(assets),
                "production_systems": len(production),
                "monitoring_coverage": round(100 * len(monitored) / max(1, len(production))),
                "control_coverage": coverage,
                "open_incidents": len(open_incidents),
                "blocked_sensitive_events": len(blocked_events),
                "model_calls_24h": calls,
                "model_spend_24h_nok": spend,
                "external_providers": len(external),
            },
            "assets": [asset.as_dict() for asset in assets],
            "controls": [control.as_dict() for control in self.controls.values()],
            "automations": [rule.as_dict() for rule in self.automations.values()],
            "automation_runs": [run.as_dict() for run in reversed(self.automation_runs[-20:])],
            "events": [event.as_dict() for event in reversed(self.events[-30:])],
            "incidents": [
                incident.as_dict()
                for incident in sorted(
                    self.incidents.values(), key=lambda item: item.created_at, reverse=True
                )
            ],
            "evidence_packs": [
                pack.as_dict()
                for pack in sorted(
                    self.evidence_packs.values(), key=lambda item: item.generated_at, reverse=True
                )
            ],
            "audit": {
                "valid": audit_valid,
                "record_count": len(self.audit_log.records()),
            },
            "data_protection": {
                "raw_prompts_retained": False,
                "sensitive_patterns": [pattern.name for pattern in PATTERNS],
                "default_unknown_destination": "block",
                "restricted_external_policy": "block",
                "confidential_approved_gateway": "redact",
            },
        }
