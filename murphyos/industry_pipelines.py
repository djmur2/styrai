"""Executable, synthetic finance and healthcare governance pipelines.

The pipelines in this module are deliberately local and deterministic.  They
exercise the real StyrAI passport, policy, approval and audit services while
using fictional source records, deterministic model adapters and local tool
adapters.  No external model, payment rail, EHR or patient-messaging system is
called.

``PipelineService`` is intentionally independent of the HTTP layer.  The web
application can expose its methods directly and can recreate the service during
the existing demonstration reset operation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from .models import ActionRequest
from .platform import GovernancePlatform, now_iso
from .service import GovernanceService


class PipelineWorkflowError(ValueError):
    """Raised when a pipeline is advanced through an invalid transition."""


def _canonical_hash(payload: Any) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _receipt(prefix: str, payload: dict[str, Any]) -> str:
    return prefix + _canonical_hash(payload)


@dataclass(frozen=True)
class StageDefinition:
    stage_id: str
    label: str
    description: str
    control_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["control_ids"] = list(self.control_ids)
        return payload


@dataclass(frozen=True)
class PipelineDefinition:
    pipeline_id: str
    industry: str
    title: str
    description: str
    source_system: str
    asset_id: str
    model_id: str
    model_version: str
    model_adapter: str
    tool: str
    operation: str
    use_case: str
    actor_id: str
    required_approver_roles: tuple[str, ...]
    modes: tuple[dict[str, str], ...]
    stages: tuple[StageDefinition, ...]


@dataclass
class PipelineStage:
    stage_id: str
    label: str
    detail: str
    status: str
    control_ids: list[str]
    timestamp: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineRun:
    run_id: str
    pipeline_id: str
    industry: str
    title: str
    mode: str
    actor: str
    case_id: str
    case: dict[str, Any]
    source_snapshot: dict[str, Any]
    started_at: str
    status: str
    current_stage: str | None
    stages: list[PipelineStage]
    operated_by: str | None = None
    approval_contexts: list[dict[str, Any]] = field(default_factory=list)
    provider_invoked: bool = False
    downstream_invoked: bool = False
    runtime_event: dict[str, Any] | None = None
    model: dict[str, Any] | None = None
    passport: dict[str, Any] | None = None
    provider_payload: str | None = None
    model_output: dict[str, Any] | None = None
    validation: dict[str, Any] | None = None
    action_payload: dict[str, Any] | None = None
    action_payload_sha256: str | None = None
    governed_action: dict[str, Any] | None = None
    execution_authorization: dict[str, Any] | None = None
    execution: dict[str, Any] | None = None
    reconciliation: dict[str, Any] | None = None
    injections: list[dict[str, Any]] = field(default_factory=list)
    linked_incident_ids: list[str] = field(default_factory=list)
    linked_automation_run_ids: list[str] = field(default_factory=list)
    completed_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(
            {
                "run_id": self.run_id,
                "pipeline_id": self.pipeline_id,
                "industry": self.industry,
                "title": self.title,
                "mode": self.mode,
                "actor": self.actor,
                "case_id": self.case_id,
                "case": self.case,
                "source_snapshot": self.source_snapshot,
                "started_at": self.started_at,
                "status": self.status,
                "current_stage": self.current_stage,
                "stages": [stage.as_dict() for stage in self.stages],
                "operated_by": self.operated_by,
                "approval_contexts": self.approval_contexts,
                "provider_invoked": self.provider_invoked,
                "downstream_invoked": self.downstream_invoked,
                "runtime_event": self.runtime_event,
                "model": self.model,
                "passport": self.passport,
                "provider_payload": self.provider_payload,
                "model_output": self.model_output,
                "validation": self.validation,
                "action_payload": self.action_payload,
                "action_payload_sha256": self.action_payload_sha256,
                "governed_action": self.governed_action,
                "execution_authorization": self.execution_authorization,
                "execution": self.execution,
                "reconciliation": self.reconciliation,
                "injections": self.injections,
                "linked_incident_ids": self.linked_incident_ids,
                "linked_automation_run_ids": self.linked_automation_run_ids,
                "completed_at": self.completed_at,
            }
        )


class SyntheticDataStore:
    """Resettable fictional records used by the local execution adapters."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, dict[str, Any]]] = {
            "finance-material-payment": {
                "FIN-PAY-8842": {
                    "case_id": "FIN-PAY-8842",
                    "title": "Nordic supplier settlement",
                    "subtitle": "Material three-payment batch",
                    "source_system": "Treasury Operations Hub",
                    "classification": "restricted",
                    "fictional": True,
                    "record_version": 1,
                    "operational_status": "held_for_ai_review",
                    "currency": "NOK",
                    "declared_total": 250_000.0,
                    "ledger_total": 250_000.0,
                    "payments": [
                        {
                            "payment_id": "PMT-101",
                            "beneficiary": "Nordhavn Supplies AS (fictional)",
                            "amount": 96_000.0,
                            "sanctions_result": "clear",
                            "duplicate": False,
                        },
                        {
                            "payment_id": "PMT-102",
                            "beneficiary": "Fjordline Components AS (fictional)",
                            "amount": 84_000.0,
                            "sanctions_result": "clear",
                            "duplicate": False,
                        },
                        {
                            "payment_id": "PMT-103",
                            "beneficiary": "Aurora Office Services AS (fictional)",
                            "amount": 70_000.0,
                            "sanctions_result": "clear",
                            "duplicate": False,
                        },
                    ],
                    "reconciliation_reference": "REC-DEMO-8842",
                    "release": None,
                },
                "FIN-PAY-9917": {
                    "case_id": "FIN-PAY-9917",
                    "title": "Month-end infrastructure settlement",
                    "subtitle": "Material two-payment batch",
                    "source_system": "Treasury Operations Hub",
                    "classification": "restricted",
                    "fictional": True,
                    "record_version": 3,
                    "operational_status": "held_for_ai_review",
                    "currency": "NOK",
                    "declared_total": 620_000.0,
                    "ledger_total": 620_000.0,
                    "payments": [
                        {
                            "payment_id": "PMT-211",
                            "beneficiary": "Polar Cloud Hosting AS (fictional)",
                            "amount": 380_000.0,
                            "sanctions_result": "clear",
                            "duplicate": False,
                        },
                        {
                            "payment_id": "PMT-212",
                            "beneficiary": "North Grid Services AS (fictional)",
                            "amount": 240_000.0,
                            "sanctions_result": "clear",
                            "duplicate": False,
                        },
                    ],
                    "reconciliation_reference": "REC-DEMO-9917",
                    "release": None,
                },
            },
            "healthcare-visit-summary": {
                "HC-VISIT-204": {
                    "case_id": "HC-VISIT-204",
                    "title": "Respiratory ward discharge",
                    "subtitle": "Visit summary and secure follow-up",
                    "source_system": "NorthCare EHR Demo",
                    "classification": "restricted",
                    "fictional": True,
                    "record_version": 2,
                    "operational_status": "awaiting_visit_summary",
                    "patient": {
                        "display_name": "Elin Sorensen (fictional)",
                        "medical_record_number": "MRN-DEMO-204",
                        "date_of_birth": "1978-04-17",
                    },
                    "encounter": {
                        "diagnosis": "Community-acquired pneumonia",
                        "observations": {
                            "temperature_c": 37.2,
                            "oxygen_saturation_percent": 96,
                        },
                        "medications": ["Doxycycline"],
                        "allergies": ["Penicillin"],
                        "follow_up": "Primary-care review within seven days",
                        "instructions": [
                            "Complete the prescribed antibiotic course",
                            "Seek urgent care if breathing worsens",
                        ],
                    },
                    "signed_summary": None,
                    "portal_queue": [],
                },
                "HC-VISIT-319": {
                    "case_id": "HC-VISIT-319",
                    "title": "Cardiology observation follow-up",
                    "subtitle": "Visit summary and monitoring plan",
                    "source_system": "NorthCare EHR Demo",
                    "classification": "restricted",
                    "fictional": True,
                    "record_version": 5,
                    "operational_status": "awaiting_visit_summary",
                    "patient": {
                        "display_name": "Jonas Vik (fictional)",
                        "medical_record_number": "MRN-DEMO-319",
                        "date_of_birth": "1965-11-03",
                    },
                    "encounter": {
                        "diagnosis": "Stable heart-failure follow-up",
                        "observations": {
                            "systolic_blood_pressure": 126,
                            "weight_kg": 82.4,
                        },
                        "medications": ["Furosemide", "Lisinopril"],
                        "allergies": [],
                        "follow_up": "Cardiology clinic review within fourteen days",
                        "instructions": [
                            "Record weight each morning",
                            "Contact the clinic if weight rises by two kilograms",
                        ],
                    },
                    "signed_summary": None,
                    "portal_queue": [],
                },
            },
        }
        # Keep an immutable copy of the fictional fixtures so a completed demo
        # scenario can be run again without requiring a full server restart.
        self._baseline_records = deepcopy(self._records)

    def prepare_for_run(
        self, pipeline_id: str, case_id: str
    ) -> tuple[dict[str, Any], bool]:
        """Return an actionable fixture, replaying completed demo cases safely.

        These records are local demonstration fixtures rather than real source
        systems. Once a previous run has produced its simulated terminal state,
        restore only that fixture before creating the next run. Unexpected
        states still fail closed instead of being silently overwritten.
        """

        try:
            current = self._records[pipeline_id][case_id]
            baseline = self._baseline_records[pipeline_id][case_id]
        except KeyError as exc:
            raise PipelineWorkflowError("Unknown synthetic case.") from exc
        if current["operational_status"] == baseline["operational_status"]:
            return deepcopy(current), False
        completed_statuses = {
            "finance-material-payment": "released_simulated",
            "healthcare-visit-summary": "summary_signed_simulated",
        }
        if current["operational_status"] != completed_statuses.get(pipeline_id):
            raise PipelineWorkflowError(
                "The synthetic case is not in an actionable demonstration state."
            )
        self._records[pipeline_id][case_id] = deepcopy(baseline)
        return deepcopy(self._records[pipeline_id][case_id]), True

    def expected_start_status(self, pipeline_id: str, case_id: str) -> str:
        try:
            return str(
                self._baseline_records[pipeline_id][case_id]["operational_status"]
            )
        except KeyError as exc:
            raise PipelineWorkflowError("Unknown synthetic case.") from exc

    def case_ids(self, pipeline_id: str) -> tuple[str, ...]:
        try:
            return tuple(self._records[pipeline_id])
        except KeyError as exc:
            raise PipelineWorkflowError("Unknown pipeline.") from exc

    def get(self, pipeline_id: str, case_id: str) -> dict[str, Any]:
        try:
            return deepcopy(self._records[pipeline_id][case_id])
        except KeyError as exc:
            raise PipelineWorkflowError("Unknown synthetic case.") from exc

    def summary(self, pipeline_id: str, case_id: str) -> dict[str, Any]:
        record = self.get(pipeline_id, case_id)
        if pipeline_id == "finance-material-payment":
            facts = [
                f"{record['currency']} {record['declared_total']:,.0f}",
                f"{len(record['payments'])} payments",
                f"Record v{record['record_version']}",
            ]
        else:
            facts = [
                record["encounter"]["diagnosis"],
                f"{len(record['encounter']['medications'])} active medicines",
                f"Record v{record['record_version']}",
            ]
        return {
            "case_id": case_id,
            "title": record["title"],
            "subtitle": record["subtitle"],
            "status": record["operational_status"],
            "classification": record["classification"],
            "fictional": True,
            "key_facts": facts,
        }

    def cases(self, pipeline_id: str) -> list[dict[str, Any]]:
        return [self.summary(pipeline_id, case_id) for case_id in self.case_ids(pipeline_id)]

    def execute_finance_release(
        self,
        *,
        case_id: str,
        expected_version: int,
        amount: float,
        receipt: str,
        executed_at: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        record = self._records["finance-material-payment"][case_id]
        before = deepcopy(record)
        if record["record_version"] != expected_version:
            raise PipelineWorkflowError("The payment batch changed after approval.")
        if record["operational_status"] != "held_for_ai_review":
            raise PipelineWorkflowError("The payment batch is no longer held for review.")
        if float(record["declared_total"]) != float(amount):
            raise PipelineWorkflowError("The approved amount no longer matches the batch.")
        record["operational_status"] = "released_simulated"
        record["record_version"] += 1
        record["release"] = {
            "released_at": executed_at,
            "amount": amount,
            "currency": record["currency"],
            "adapter_receipt": receipt,
            "external_side_effect": False,
        }
        return before, deepcopy(record)

    def execute_healthcare_summary(
        self,
        *,
        case_id: str,
        expected_version: int,
        summary: dict[str, Any],
        receipt: str,
        executed_at: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        record = self._records["healthcare-visit-summary"][case_id]
        before = deepcopy(record)
        if record["record_version"] != expected_version:
            raise PipelineWorkflowError("The encounter changed after approval.")
        if record["operational_status"] != "awaiting_visit_summary":
            raise PipelineWorkflowError("The encounter is no longer awaiting a summary.")
        record["operational_status"] = "summary_signed_simulated"
        record["record_version"] += 1
        record["signed_summary"] = deepcopy(summary)
        record["signed_summary"]["signed_at"] = executed_at
        record["signed_summary"]["adapter_receipt"] = receipt
        record["portal_queue"].append(
            {
                "message_type": "secure_visit_summary",
                "queued_at": executed_at,
                "status": "queued_simulated",
                "external_side_effect": False,
            }
        )
        return before, deepcopy(record)


STAGES = (
    StageDefinition(
        "source",
        "Load source record",
        "Read a fictional source record and establish its version and classification.",
        ("AI-INV-01", "EVID-01"),
    ),
    StageDefinition(
        "input_control",
        "Control model input",
        "Minimise the input and enforce model, destination and data controls.",
        ("DATA-OUT-01", "MODEL-USE-02"),
    ),
    StageDefinition(
        "model",
        "Run approved model",
        "Invoke a deterministic model adapter through the approved route.",
        ("MODEL-USE-02", "MON-01"),
    ),
    StageDefinition(
        "validation",
        "Validate model output",
        "Check the output against authoritative source facts before any action.",
        ("MON-01", "INC-01"),
    ),
    StageDefinition(
        "action",
        "Propose governed action",
        "Bind the validated output, target and exact model version to policy.",
        ("MODEL-USE-02", "EVID-01"),
    ),
    StageDefinition(
        "approval",
        "Independent human review",
        "Hold the consequential action for a named, separate reviewer.",
        ("HUMAN-01",),
    ),
    StageDefinition(
        "execute",
        "Execute simulated adapter",
        "Verify the bound receipt and invoke the idempotent demonstration adapter.",
        ("HUMAN-01", "EVID-01"),
    ),
    StageDefinition(
        "reconcile",
        "Reconcile outcome",
        "Compare the approved action with the resulting source-system state.",
        ("EVID-01", "MON-01"),
    ),
)


PIPELINES = (
    PipelineDefinition(
        pipeline_id="finance-material-payment",
        industry="financial_services",
        title="Material payment release",
        description=(
            "Assess a fictional payment batch, validate the recommendation, obtain "
            "two independent approvals and release it through a simulated adapter."
        ),
        source_system="Treasury Operations Hub",
        asset_id="agent-payment-ops",
        model_id="approved-operations-model",
        model_version="2026-08-15",
        model_adapter="local-payment-risk-model",
        tool="payments",
        operation="release",
        use_case="payment_operations",
        actor_id="payments-operator-demo",
        required_approver_roles=("payments_manager", "finance_controller"),
        modes=(
            {"id": "standard", "label": "Successful controlled release", "kind": "positive"},
            {"id": "mismatch", "label": "Block an amount mismatch", "kind": "negative"},
            {"id": "unapproved_destination", "label": "Block an unapproved model route", "kind": "negative"},
        ),
        stages=STAGES,
    ),
    PipelineDefinition(
        pipeline_id="healthcare-visit-summary",
        industry="healthcare",
        title="Clinical visit summary",
        description=(
            "Create a fictional visit summary, validate it against the encounter, "
            "obtain clinician approval and write it to a local EHR adapter."
        ),
        source_system="NorthCare EHR Demo",
        asset_id="agent-healthcare-visit-summary",
        model_id="clinical-summary-model",
        model_version="2026-08-2",
        model_adapter="local-clinical-summary-model",
        tool="patient_portal",
        operation="publish_summary",
        use_case="patient_visit_summary",
        actor_id="care-coordinator-demo",
        required_approver_roles=("attending_clinician",),
        modes=(
            {"id": "standard", "label": "Successful controlled EHR write", "kind": "positive"},
            {"id": "unsupported_output", "label": "Block an unsupported clinical output", "kind": "negative"},
            {"id": "unapproved_destination", "label": "Block an unapproved model route", "kind": "negative"},
        ),
        stages=STAGES,
    ),
)


DEMO_IDENTITIES = {
    "payments-operator-demo": {"role": "payments_operator", "label": "Payments operator"},
    "payments-manager-demo": {"role": "payments_manager", "label": "Payments manager"},
    "treasury-controller-demo": {"role": "finance_controller", "label": "Treasury controller"},
    "care-coordinator-demo": {"role": "care_coordinator", "label": "Care coordinator"},
    "attending-clinician-demo": {"role": "attending_clinician", "label": "Attending clinician"},
    "clinical-safety-officer-demo": {"role": "attending_clinician", "label": "Clinical safety officer"},
}


class PipelineService:
    """Coordinate source data, model controls, approval, execution and evidence."""

    TERMINAL_STATUSES = {"blocked", "denied", "executed"}

    def __init__(
        self,
        service: GovernanceService,
        platform: GovernancePlatform,
        data_store: SyntheticDataStore | None = None,
    ) -> None:
        self.service = service
        self.platform = platform
        self.data_store = data_store or SyntheticDataStore()
        self._definitions = {item.pipeline_id: item for item in PIPELINES}
        self.runs: dict[str, PipelineRun] = {}
        self.latest_run_id: str | None = None
        self._execution_cache: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def catalog(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for definition in self._definitions.values():
            approvers = [
                {"approver_id": identity, **details}
                for identity, details in DEMO_IDENTITIES.items()
                if details["role"] in definition.required_approver_roles
            ]
            result.append(
                {
                    "pipeline_id": definition.pipeline_id,
                    "industry": definition.industry,
                    "title": definition.title,
                    "description": definition.description,
                    "source_system": definition.source_system,
                    "model": {
                        "asset_id": definition.asset_id,
                        "model_id": definition.model_id,
                        "version": definition.model_version,
                        "adapter": definition.model_adapter,
                    },
                    "action": {
                        "tool": definition.tool,
                        "operation": definition.operation,
                    },
                    "modes": [dict(mode) for mode in definition.modes],
                    "stages": [stage.as_dict() for stage in definition.stages],
                    "cases": self.data_store.cases(definition.pipeline_id),
                    "actor": {
                        "actor_id": definition.actor_id,
                        **DEMO_IDENTITIES[definition.actor_id],
                    },
                    "approvers": approvers,
                    "simulation": {
                        "external_model_connected": False,
                        "external_tool_connected": False,
                        "governance_path_live": True,
                    },
                }
            )
        return result

    def state(self) -> dict[str, Any]:
        with self._lock:
            latest = self.runs.get(self.latest_run_id or "")
            return {
                "catalog": self.catalog(),
                "runs": [run.as_dict() for run in reversed(tuple(self.runs.values()))],
                "latest_run": latest.as_dict() if latest else None,
            }

    def cases(self, pipeline_id: str) -> list[dict[str, Any]]:
        self._definition(pipeline_id)
        return self.data_store.cases(pipeline_id)

    def case_record(self, pipeline_id: str, case_id: str) -> dict[str, Any]:
        self._definition(pipeline_id)
        return self.data_store.get(pipeline_id, case_id)

    def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a run, optionally advancing it immediately to human review.

        Accepted fields are ``pipeline_id`` (or ``scenario``), ``case_id``,
        ``actor``, ``mode`` and the optional boolean ``run_to_review``.
        """

        pipeline_id = str(
            payload.get("pipeline_id") or payload.get("scenario") or ""
        )
        definition = self._definition(pipeline_id)
        case_id = str(payload.get("case_id") or self.data_store.case_ids(pipeline_id)[0])
        mode = str(payload.get("mode", "standard"))
        allowed_modes = {item["id"] for item in definition.modes}
        if mode not in allowed_modes:
            raise PipelineWorkflowError("Unknown pipeline mode.")
        operated_by = str(payload.get("operated_by", "")).strip() or None
        actor = str(
            definition.actor_id
            if operated_by is not None
            else payload.get("actor") or definition.actor_id
        ).strip()
        if not actor:
            raise PipelineWorkflowError("An initiating actor is required.")
        with self._lock:
            source, fixture_replayed = self.data_store.prepare_for_run(
                pipeline_id, case_id
            )
            steps = [
                PipelineStage(
                    stage_id=stage.stage_id,
                    label=stage.label,
                    detail=stage.description,
                    status="ready" if index == 0 else "pending",
                    control_ids=list(stage.control_ids),
                )
                for index, stage in enumerate(definition.stages)
            ]
            run = PipelineRun(
                run_id="PIPE-" + uuid4().hex[:10].upper(),
                pipeline_id=pipeline_id,
                industry=definition.industry,
                title=definition.title,
                mode=mode,
                actor=actor,
                case_id=case_id,
                case=self.data_store.summary(pipeline_id, case_id),
                source_snapshot=source,
                started_at=now_iso(),
                status="created",
                current_stage="source",
                stages=steps,
                operated_by=operated_by,
                passport=self._passport_view(definition),
            )
            self.runs[run.run_id] = run
            self.latest_run_id = run.run_id
            self.service.audit_log.append(
                "pipeline.created",
                run.run_id,
                {
                    "pipeline_id": run.pipeline_id,
                    "industry": run.industry,
                    "case_id": run.case_id,
                    "mode": run.mode,
                    "actor": run.actor,
                    "operated_by": run.operated_by,
                    "source_snapshot_sha256": _canonical_hash(source),
                    "source_classification": source["classification"],
                    "synthetic_data": True,
                    "fixture_replayed": fixture_replayed,
                },
            )
            if bool(payload.get("run_to_review", False)):
                return self.advance(run.run_id, until="review")
            return run.as_dict()

    def advance(self, run_id: str, until: str = "next") -> dict[str, Any]:
        """Advance one stage, or continue until a review/terminal state."""

        if until not in {"next", "review"}:
            raise PipelineWorkflowError("Advance mode must be 'next' or 'review'.")
        with self._lock:
            run = self._run(run_id)
            if run.status in self.TERMINAL_STATUSES or run.status in {
                "waiting_approval",
                "authorized",
            }:
                return run.as_dict()
            while True:
                stage_id = run.current_stage
                if stage_id == "source":
                    self._load_source(run)
                elif stage_id == "input_control":
                    self._control_input(run)
                elif stage_id == "model":
                    self._run_model(run)
                elif stage_id == "validation":
                    self._validate_output(run)
                elif stage_id == "action":
                    self._propose_action(run)
                else:
                    raise PipelineWorkflowError("The pipeline is not ready to advance.")
                if until == "next":
                    return run.as_dict()
                if run.status in self.TERMINAL_STATUSES or run.status in {
                    "waiting_approval",
                    "authorized",
                }:
                    return run.as_dict()

    def decide(
        self,
        run_id: str,
        approver_id: str,
        approved: bool,
        rationale: str,
        demonstration_approver_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            run = self._run(run_id)
            if run.status != "waiting_approval" or not run.governed_action:
                raise PipelineWorkflowError("The pipeline is not waiting for approval.")
            demo_approver_id = demonstration_approver_id or approver_id
            identity = DEMO_IDENTITIES.get(demo_approver_id)
            definition = self._definition(run.pipeline_id)
            if identity is None or identity["role"] not in definition.required_approver_roles:
                raise PipelineWorkflowError("This demonstration identity is not an approved reviewer for the pipeline.")
            if demo_approver_id == run.actor:
                raise PipelineWorkflowError("The pipeline initiator cannot approve the action.")
            if any(
                item["demonstration_approver_id"] == demo_approver_id
                for item in run.approval_contexts
            ):
                raise PipelineWorkflowError(
                    "Each demonstration reviewer role can be used only once."
                )
            action_id = run.governed_action["action"]["action_id"]
            governed = self.service.decide_approval(
                action_id=action_id,
                approver_id=approver_id,
                approved=approved,
                rationale=rationale,
            )
            run.governed_action = governed.as_dict()
            approval_context = {
                "approver_id": approver_id,
                "demonstration_approver_id": demo_approver_id,
                "demonstration_role": identity["role"],
                "approved": approved,
            }
            run.approval_contexts.append(approval_context)
            self.service.audit_log.append(
                "pipeline.approval_attributed",
                run.run_id,
                approval_context,
            )
            step = self._step(run, "approval")
            step.timestamp = now_iso()
            if not approved:
                step.status = "blocked"
                step.detail = "The independent reviewer denied the proposed action."
                self._skip_after(run, "approval")
                run.status = "denied"
                run.current_stage = None
                run.completed_at = now_iso()
                return run.as_dict()
            if governed.status.value != "authorized":
                step.status = "waiting"
                step.detail = (
                    f"{len(governed.approved_by)} of "
                    f"{governed.decision.required_approvals} independent approvals recorded."
                )
                return run.as_dict()

            step.status = "complete"
            step.detail = "All required independent approvals are recorded."
            execute_step = self._step(run, "execute")
            execute_step.status = "ready"
            run.current_stage = "execute"
            run.status = "authorized"
            authorization_claims = {
                "run_id": run.run_id,
                "action_id": action_id,
                "governance_receipt": governed.authorization_receipt,
                "action_payload_sha256": run.action_payload_sha256,
                "model_output_sha256": run.model["output_sha256"] if run.model else None,
                "approvers": sorted(governed.approved_by),
            }
            run.execution_authorization = {
                **authorization_claims,
                "receipt": _receipt(
                    "styrai_pipeline_auth_v1_", authorization_claims
                ),
            }
            self.service.audit_log.append(
                "pipeline.execution_authorized",
                run.run_id,
                {
                    **authorization_claims,
                    "pipeline_authorization_receipt": run.execution_authorization[
                        "receipt"
                    ],
                },
            )
            return run.as_dict()

    def execute(self, run_id: str) -> dict[str, Any]:
        """Execute the exactly approved payload once, then reconcile it."""

        with self._lock:
            run = self._run(run_id)
            if run.status == "executed" and run.execution:
                return run.as_dict()
            if run.status != "authorized" or not run.governed_action:
                raise PipelineWorkflowError("Execution requires an authorized pipeline action.")
            if not run.action_payload or not run.action_payload_sha256:
                raise PipelineWorkflowError("The approved action payload is unavailable.")
            actual_payload_hash = _canonical_hash(run.action_payload)
            if actual_payload_hash != run.action_payload_sha256:
                raise PipelineWorkflowError("The action payload changed after approval.")
            authorization = run.execution_authorization
            if not authorization:
                raise PipelineWorkflowError("A pipeline authorization receipt is required.")
            authorization_claims = {
                key: authorization[key]
                for key in (
                    "run_id",
                    "action_id",
                    "governance_receipt",
                    "action_payload_sha256",
                    "model_output_sha256",
                    "approvers",
                )
            }
            expected_authorization_receipt = _receipt(
                "styrai_pipeline_auth_v1_", authorization_claims
            )
            if authorization["receipt"] != expected_authorization_receipt:
                raise PipelineWorkflowError("The pipeline authorization receipt is invalid.")
            if authorization["action_payload_sha256"] != actual_payload_hash:
                raise PipelineWorkflowError("The authorization does not bind this payload.")
            current_governed = self.service.assert_authorized(
                authorization["action_id"]
            )
            if not hmac.compare_digest(
                current_governed.authorization_receipt or "",
                str(authorization["governance_receipt"]),
            ):
                raise PipelineWorkflowError(
                    "The current governance receipt does not match the pipeline authorization."
                )

            idempotency_key = _canonical_hash(
                {
                    "run_id": run.run_id,
                    "action_id": authorization["action_id"],
                    "action_payload_sha256": actual_payload_hash,
                }
            )
            cached = self._execution_cache.get(idempotency_key)
            if cached is not None:
                run.execution = deepcopy(cached)
                run.status = "executed"
                return run.as_dict()

            executed_at = now_iso()
            expected_after_version = int(run.action_payload["expected_version"]) + 1
            adapter_name = (
                "local-demo-payment-ledger-adapter"
                if run.pipeline_id == "finance-material-payment"
                else "local-demo-ehr-adapter"
            )
            receipt_claims = {
                "run_id": run.run_id,
                "action_id": authorization["action_id"],
                "pipeline_authorization_receipt": authorization["receipt"],
                "action_payload_sha256": actual_payload_hash,
                "adapter": adapter_name,
                "target_id": run.case_id,
                "before_version": run.action_payload["expected_version"],
                "after_version": expected_after_version,
                "outcome": "simulated_executed",
            }
            adapter_receipt = _receipt("styrai_adapter_v1_", receipt_claims)
            if run.pipeline_id == "finance-material-payment":
                before, after = self.data_store.execute_finance_release(
                    case_id=run.case_id,
                    expected_version=int(run.action_payload["expected_version"]),
                    amount=float(run.action_payload["amount"]),
                    receipt=adapter_receipt,
                    executed_at=executed_at,
                )
            else:
                before, after = self.data_store.execute_healthcare_summary(
                    case_id=run.case_id,
                    expected_version=int(run.action_payload["expected_version"]),
                    summary=deepcopy(run.action_payload["summary"]),
                    receipt=adapter_receipt,
                    executed_at=executed_at,
                )
            run.downstream_invoked = True
            run.execution = {
                **receipt_claims,
                "idempotency_key": idempotency_key,
                "adapter_receipt": adapter_receipt,
                "executed_at": executed_at,
                "external_side_effect": False,
                "before_record": before,
                "after_record": after,
            }
            self._execution_cache[idempotency_key] = deepcopy(run.execution)
            execute_step = self._step(run, "execute")
            execute_step.status = "complete"
            execute_step.detail = (
                "The demonstration adapter executed the exact receipt-bound action once."
            )
            execute_step.timestamp = executed_at
            self.service.audit_log.append(
                "pipeline.tool_executed",
                run.run_id,
                {
                    **receipt_claims,
                    "idempotency_key": idempotency_key,
                    "adapter_receipt": adapter_receipt,
                    "external_side_effect": False,
                    "source_data_stored": False,
                },
            )
            self._reconcile(run)
            run.case = self.data_store.summary(run.pipeline_id, run.case_id)
            run.status = "executed"
            run.current_stage = None
            run.completed_at = now_iso()
            return run.as_dict()

    def reconcile(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._run(run_id)
            if not run.execution:
                raise PipelineWorkflowError("Reconciliation requires an execution outcome.")
            self._reconcile(run)
            return run.as_dict()

    def inject(self, target: str, kind: str) -> dict[str, Any]:
        """Inject a drift or version-change event for a run or pipeline."""

        if kind not in {"drift", "version"}:
            raise PipelineWorkflowError("Injection kind must be 'drift' or 'version'.")
        with self._lock:
            run = self.runs.get(target)
            pipeline_id = run.pipeline_id if run else target
            definition = self._definition(pipeline_id)
            if kind == "drift":
                result = self.platform.simulate_health_breach(
                    definition.asset_id, "drift"
                )
            else:
                result = self.platform.simulate_version_change(definition.asset_id)
            incident_id = result["incident"]["incident_id"]
            automation_run_id = result["automation_run"]["run_id"]
            if run is None:
                return {
                    "pipeline_id": pipeline_id,
                    "kind": kind,
                    "incident_id": incident_id,
                    "automation_run_id": automation_run_id,
                    "result": result,
                }
            run.injections.append(
                {
                    "kind": kind,
                    "injected_at": now_iso(),
                    "incident_id": incident_id,
                    "automation_run_id": automation_run_id,
                    "asset_status": result["asset"]["status"],
                }
            )
            self._link_platform_objects(run, result)
            if run.status not in self.TERMINAL_STATUSES:
                self._block(
                    run,
                    "A monitoring control paused the pipeline before downstream execution.",
                    failure_code=(
                        "model_drift_detected"
                        if kind == "drift"
                        else "unapproved_model_version"
                    ),
                )
            return run.as_dict()

    def evidence(self, run_id: str) -> dict[str, Any]:
        """Return correlated metadata-only evidence for a pipeline run."""

        with self._lock:
            run = self._run(run_id)
            action_id = (
                run.governed_action["action"]["action_id"]
                if run.governed_action
                else None
            )
            runtime_event_id = (
                run.runtime_event.get("event_id") if run.runtime_event else None
            )
            identifiers = {
                run.run_id,
                action_id,
                runtime_event_id,
                *run.linked_incident_ids,
                *run.linked_automation_run_ids,
            }
            records = [
                record
                for record in self.service.audit_log.records()
                if record["action_id"] in identifiers
                or record.get("payload", {}).get("run_id") == run.run_id
                or record.get("payload", {}).get("runtime_event_id")
                == runtime_event_id
                or record.get("payload", {}).get("action_id") == action_id
            ]
            public_run = run.as_dict()
            public_run["case"] = {
                "case_id": run.case_id,
                "industry": run.industry,
                "classification": run.source_snapshot["classification"],
                "fictional": True,
            }
            public_run["source_snapshot"] = {
                "case_id": run.case_id,
                "source_system": run.source_snapshot["source_system"],
                "classification": run.source_snapshot["classification"],
                "snapshot_sha256": _canonical_hash(run.source_snapshot),
                "content_included": False,
            }
            public_run["provider_payload"] = None
            public_run["model_output"] = None
            public_run["action_payload"] = None
            if public_run.get("runtime_event"):
                public_run["runtime_event"]["redacted_preview"] = None
            if public_run.get("execution"):
                public_run["execution"].pop("before_record", None)
                public_run["execution"].pop("after_record", None)
            if public_run.get("validation"):
                public_run["validation"] = {
                    "status": public_run["validation"]["status"],
                    "failure_codes": public_run["validation"]["failure_codes"],
                    "checks": [
                        {
                            "check_id": check["check_id"],
                            "passed": check["passed"],
                        }
                        for check in public_run["validation"]["checks"]
                    ],
                }
            return {
                "schema": "styrai.pipeline-evidence.v1",
                "run": public_run,
                "audit_records": records,
                "audit_chain_valid": self.service.audit_log.verify(),
                "hashes": {
                    "source_snapshot_sha256": _canonical_hash(run.source_snapshot),
                    "provider_payload_sha256": (
                        _canonical_hash(run.provider_payload)
                        if run.provider_payload is not None
                        else None
                    ),
                    "model_output_sha256": (
                        run.model.get("output_sha256") if run.model else None
                    ),
                    "action_payload_sha256": run.action_payload_sha256,
                },
                "data_statement": (
                    "All records are fictional. Source content, provider payloads, "
                    "model output and tool payloads are excluded from evidence; "
                    "only metadata, hashes, decisions and receipts are retained."
                ),
                "disclaimer": (
                    "The model and downstream adapters are deterministic local "
                    "fixtures. The governance, approval, validation, execution gate, "
                    "reconciliation and hash-chained evidence paths execute live."
                ),
            }

    def _definition(self, pipeline_id: str) -> PipelineDefinition:
        try:
            return self._definitions[pipeline_id]
        except KeyError as exc:
            raise PipelineWorkflowError("Unknown pipeline.") from exc

    def _run(self, run_id: str) -> PipelineRun:
        try:
            return self.runs[run_id]
        except KeyError as exc:
            raise PipelineWorkflowError("Unknown pipeline run.") from exc

    @staticmethod
    def _step(run: PipelineRun, stage_id: str) -> PipelineStage:
        try:
            return next(step for step in run.stages if step.stage_id == stage_id)
        except StopIteration as exc:
            raise PipelineWorkflowError("Unknown pipeline stage.") from exc

    @staticmethod
    def _next_stage(run: PipelineRun, stage_id: str) -> None:
        index = next(
            index for index, stage in enumerate(run.stages) if stage.stage_id == stage_id
        )
        if index + 1 >= len(run.stages):
            run.current_stage = None
            return
        following = run.stages[index + 1]
        if following.status == "pending":
            following.status = "ready"
        run.current_stage = following.stage_id

    @staticmethod
    def _complete_step(run: PipelineRun, stage_id: str, detail: str) -> None:
        step = PipelineService._step(run, stage_id)
        step.status = "complete"
        step.detail = detail
        step.timestamp = now_iso()

    @staticmethod
    def _skip_after(run: PipelineRun, stage_id: str) -> None:
        found = False
        for step in run.stages:
            if found and step.status in {"pending", "ready", "waiting"}:
                step.status = "skipped"
                step.timestamp = None
            if step.stage_id == stage_id:
                found = True

    def _passport_view(self, definition: PipelineDefinition) -> dict[str, Any]:
        registry = self.service.registry
        if registry is None:
            return {
                "registry_version": None,
                "model_id": definition.model_id,
                "version": definition.model_version,
                "status": "registry_not_enforced",
            }
        passport = next(
            (
                item
                for item in registry.passports()
                if item.model_id == definition.model_id
                and item.version == definition.model_version
            ),
            None,
        )
        if passport is None:
            return {
                "registry_version": registry.version,
                "model_id": definition.model_id,
                "version": definition.model_version,
                "status": "not_registered",
            }
        return {
            "registry_version": registry.version,
            "model_id": passport.model_id,
            "version": passport.version,
            "provider": passport.provider,
            "owner": passport.owner,
            "risk_tier": passport.risk_tier,
            "status": passport.status,
            "intended_uses": list(passport.intended_uses),
            "allowed_tools": list(passport.allowed_tools),
            "allowed_classifications": list(passport.allowed_classifications),
        }

    def _load_source(self, run: PipelineRun) -> None:
        current = self.data_store.get(run.pipeline_id, run.case_id)
        if current["record_version"] != run.source_snapshot["record_version"]:
            self._block(run, "The source record changed before processing.", "source_version_changed")
            return
        expected_status = self.data_store.expected_start_status(
            run.pipeline_id, run.case_id
        )
        if current["operational_status"] != expected_status:
            self._block(
                run,
                "The source record is no longer in an actionable state.",
                "source_state_changed",
            )
            return
        self._complete_step(
            run,
            "source",
            "The fictional source record and immutable version were loaded.",
        )
        run.status = "source_loaded"
        self._next_stage(run, "source")
        self.service.audit_log.append(
            "pipeline.source_loaded",
            run.run_id,
            {
                "pipeline_id": run.pipeline_id,
                "case_id": run.case_id,
                "record_version": current["record_version"],
                "classification": current["classification"],
                "snapshot_sha256": _canonical_hash(current),
                "content_stored": False,
            },
        )

    def _provider_input(self, run: PipelineRun) -> str:
        source = run.source_snapshot
        if run.pipeline_id == "finance-material-payment":
            payments = source["payments"]
            calculated_total = sum(float(item["amount"]) for item in payments)
            clear_count = sum(item["sanctions_result"] == "clear" for item in payments)
            duplicate_count = sum(bool(item["duplicate"]) for item in payments)
            return (
                f"Assess batch {run.case_id}: currency {source['currency']}; "
                f"declared total {source['declared_total']:.2f}; calculated total "
                f"{calculated_total:.2f}; ledger total {source['ledger_total']:.2f}; "
                f"payment count {len(payments)}; sanctions clear {clear_count}; "
                f"duplicates {duplicate_count}. Direct account data was removed."
            )
        encounter = source["encounter"]
        return (
            f"Prepare a de-identified visit summary. Diagnosis: "
            f"{encounter['diagnosis']}. Observations: "
            f"{json.dumps(encounter['observations'], sort_keys=True)}. Medicines: "
            f"{', '.join(encounter['medications']) or 'none'}. Allergies: "
            f"{', '.join(encounter['allergies']) or 'none recorded'}. Follow-up: "
            f"{encounter['follow_up']}. Direct patient identifiers were removed."
        )

    def _control_input(self, run: PipelineRun) -> None:
        definition = self._definition(run.pipeline_id)
        target_asset_id = (
            "shadow-public-ai"
            if run.mode == "unapproved_destination"
            else definition.asset_id
        )
        asset = self.platform.assets.get(target_asset_id)
        if asset is None:
            self._block(run, "The pipeline model asset is not registered.", "model_asset_not_registered")
            return
        if run.mode != "unapproved_destination" and (
            asset.version != definition.model_version
            or asset.approved_version != definition.model_version
        ):
            self._block(run, "The runtime model version does not match the pipeline passport.", "unapproved_model_version")
            return
        if run.mode != "unapproved_destination" and asset.health.status in {
            "degraded",
            "paused",
            "blocked",
        }:
            self._block(run, "Model monitoring has paused this route.", "model_health_guard")
            return
        provider_payload = self._provider_input(run)
        classification = (
            "internal"
            if run.pipeline_id == "finance-material-payment"
            else "confidential"
        )
        result = self.platform.simulate_model_call(
            {
                "asset_id": target_asset_id,
                "actor": run.actor,
                "classification": classification,
                "prompt": provider_payload,
            }
        )
        event = result["event"]
        run.runtime_event = {
            key: value
            for key, value in event.items()
            if key != "redacted_preview"
        }
        run.provider_payload = event["redacted_preview"]
        self._link_platform_objects(run, result)
        if event["decision"] not in {
            "allowed",
            "allow_with_redaction",
            # The current platform expresses approved, customer-hosted restricted
            # processing as pending human oversight.  This pipeline fulfils that
            # obligation at the consequential publish step below; no external
            # destination is used in the meantime.
            "pending_approval",
        }:
            self._block(
                run,
                event["reason"],
                "unapproved_destination"
                if run.mode == "unapproved_destination"
                else "runtime_policy_block",
                stage_id="input_control",
            )
            return
        self._complete_step(
            run,
            "input_control",
            "The provider payload was minimised and the approved destination passed runtime controls.",
        )
        run.status = "input_controlled"
        self._next_stage(run, "input_control")

    def _run_model(self, run: PipelineRun) -> None:
        if run.provider_payload is None or run.runtime_event is None:
            raise PipelineWorkflowError("A controlled provider payload is required.")
        definition = self._definition(run.pipeline_id)
        if run.pipeline_id == "finance-material-payment":
            output = self._finance_model_output(run)
        else:
            output = self._healthcare_model_output(run)
        run.provider_invoked = True
        run.model_output = output
        run.model = {
            "asset_id": definition.asset_id,
            "model_id": definition.model_id,
            "version": definition.model_version,
            "adapter": definition.model_adapter,
            "runtime_event_id": run.runtime_event["event_id"],
            "input_sha256": _canonical_hash(run.provider_payload),
            "output_sha256": _canonical_hash(output),
            "external_side_effect": False,
        }
        self._complete_step(
            run,
            "model",
            "The deterministic model adapter returned an output bound to the approved version.",
        )
        run.status = "model_completed"
        self._next_stage(run, "model")
        self.service.audit_log.append(
            "pipeline.model_executed",
            run.run_id,
            {
                "pipeline_id": run.pipeline_id,
                "runtime_event_id": run.runtime_event["event_id"],
                "model_id": definition.model_id,
                "model_version": definition.model_version,
                "adapter": definition.model_adapter,
                "input_sha256": run.model["input_sha256"],
                "output_sha256": run.model["output_sha256"],
                "input_stored": False,
                "output_stored": False,
                "external_side_effect": False,
            },
        )

    @staticmethod
    def _finance_model_output(run: PipelineRun) -> dict[str, Any]:
        source = run.source_snapshot
        payments = source["payments"]
        calculated_total = round(sum(float(item["amount"]) for item in payments), 2)
        release_amount = (
            calculated_total + 1_000.0 if run.mode == "mismatch" else calculated_total
        )
        risk_flags: list[str] = []
        if any(item["sanctions_result"] != "clear" for item in payments):
            risk_flags.append("sanctions_review_required")
        if any(item["duplicate"] for item in payments):
            risk_flags.append("possible_duplicate")
        reconciled = calculated_total == float(source["declared_total"]) == float(
            source["ledger_total"]
        )
        return {
            "recommendation": "release" if reconciled and not risk_flags else "hold",
            "recommended_release_amount": release_amount,
            "currency": source["currency"],
            "calculated_total": calculated_total,
            "payment_count": len(payments),
            "reconciliation_passed": reconciled,
            "risk_flags": risk_flags,
            "reason_codes": (
                ["totals_reconciled", "sanctions_clear", "no_duplicates"]
                if reconciled and not risk_flags
                else risk_flags
            ),
        }

    @staticmethod
    def _healthcare_model_output(run: PipelineRun) -> dict[str, Any]:
        encounter = run.source_snapshot["encounter"]
        medicines = list(encounter["medications"])
        diagnosis = encounter["diagnosis"]
        recommendations = list(encounter["instructions"])
        if run.mode == "unsupported_output":
            medicines.append("Amoxicillin")
            diagnosis = "Severe bacterial sepsis"
            recommendations.append("Start an unrecorded antibiotic immediately")
        return {
            "summary": (
                f"Visit reviewed for {diagnosis}. Current medicines: "
                f"{', '.join(medicines) or 'none recorded'}."
            ),
            "diagnosis": diagnosis,
            "medications": medicines,
            "follow_up": encounter["follow_up"],
            "patient_instructions": recommendations,
            "recommended_action": "sign_and_queue_secure_summary",
        }

    def _validate_output(self, run: PipelineRun) -> None:
        if run.model_output is None:
            raise PipelineWorkflowError("A model output is required for validation.")
        if run.pipeline_id == "finance-material-payment":
            validation = self._validate_finance(run)
        else:
            validation = self._validate_healthcare(run)
        run.validation = validation
        if validation["status"] != "passed":
            platform_result = self._validation_incident(run, validation)
            if platform_result:
                self._link_platform_objects(run, platform_result)
            self._block(
                run,
                "Post-model validation blocked the output before action proposal.",
                validation["failure_codes"][0],
                stage_id="validation",
                preserve_validation=True,
            )
            return
        self._complete_step(
            run,
            "validation",
            "Every authoritative-data and safety check passed before action proposal.",
        )
        run.status = "validation_passed"
        self._next_stage(run, "validation")
        self.service.audit_log.append(
            "pipeline.output_validated",
            run.run_id,
            {
                "pipeline_id": run.pipeline_id,
                "model_output_sha256": run.model["output_sha256"] if run.model else None,
                "status": "passed",
                "check_ids": [check["check_id"] for check in validation["checks"]],
            },
        )

    @staticmethod
    def _validate_finance(run: PipelineRun) -> dict[str, Any]:
        source = run.source_snapshot
        output = run.model_output or {}
        checks = [
            {
                "check_id": "amount_matches_authoritative_batch",
                "label": "Recommended amount matches the source batch",
                "passed": float(output.get("recommended_release_amount", -1))
                == float(source["declared_total"]),
                "detail": "Compared with the authoritative batch total.",
            },
            {
                "check_id": "ledger_reconciled",
                "label": "Payment and ledger totals reconcile",
                "passed": bool(output.get("reconciliation_passed"))
                and float(source["declared_total"]) == float(source["ledger_total"]),
                "detail": "Compared payment, declared and ledger totals.",
            },
            {
                "check_id": "payment_count_matches",
                "label": "Payment count matches the source batch",
                "passed": int(output.get("payment_count", -1)) == len(source["payments"]),
                "detail": "Compared with the immutable source snapshot.",
            },
            {
                "check_id": "screening_clear",
                "label": "Sanctions and duplicate screening is clear",
                "passed": not output.get("risk_flags")
                and all(
                    item["sanctions_result"] == "clear" and not item["duplicate"]
                    for item in source["payments"]
                ),
                "detail": "No unresolved risk flag may reach release approval.",
            },
        ]
        failed = [check["check_id"] for check in checks if not check["passed"]]
        return {
            "status": "passed" if not failed else "failed",
            "checks": checks,
            "failure_codes": failed,
        }

    @staticmethod
    def _validate_healthcare(run: PipelineRun) -> dict[str, Any]:
        encounter = run.source_snapshot["encounter"]
        output = run.model_output or {}
        source_medicines = {item.casefold() for item in encounter["medications"]}
        output_medicines = {
            str(item).casefold() for item in output.get("medications", [])
        }
        allergies = {item.casefold() for item in encounter["allergies"]}
        contraindicated = "penicillin" in allergies and "amoxicillin" in output_medicines
        checks = [
            {
                "check_id": "diagnosis_supported",
                "label": "Diagnosis is supported by the encounter",
                "passed": output.get("diagnosis") == encounter["diagnosis"],
                "detail": "Compared with the clinician-authored encounter diagnosis.",
            },
            {
                "check_id": "medications_supported",
                "label": "Medicines are present in the encounter",
                "passed": output_medicines.issubset(source_medicines),
                "detail": "No medicine may be introduced by the summary model.",
            },
            {
                "check_id": "allergy_conflict_absent",
                "label": "No medicine conflicts with a recorded allergy",
                "passed": not contraindicated,
                "detail": "A deterministic allergy rule checks the proposed output.",
            },
            {
                "check_id": "follow_up_supported",
                "label": "Follow-up plan matches the encounter",
                "passed": output.get("follow_up") == encounter["follow_up"],
                "detail": "Compared with the clinician-authored follow-up plan.",
            },
        ]
        failed = [check["check_id"] for check in checks if not check["passed"]]
        return {
            "status": "passed" if not failed else "failed",
            "checks": checks,
            "failure_codes": failed,
        }

    def _validation_incident(
        self, run: PipelineRun, validation: dict[str, Any]
    ) -> dict[str, Any] | None:
        create_incident = getattr(self.platform, "_create_incident", None)
        record_automation = getattr(self.platform, "_record_automation_run", None)
        if not callable(create_incident) or not callable(record_automation):
            return None
        incident = create_incident(
            severity="high",
            title="Post-model output validation blocked",
            category="model_output_validation",
            asset_id=self._definition(run.pipeline_id).asset_id,
            summary=(
                "One or more deterministic source-of-truth checks failed; no "
                "governed action or downstream execution was created."
            ),
            automated_actions=(
                "Blocked the model output",
                "Prevented action proposal",
                "Preserved metadata-only validation evidence",
            ),
            owner=(
                "Model Risk"
                if run.industry == "financial_services"
                else "Clinical Safety"
            ),
        )
        automation = record_automation(
            "AUTO-DRIFT",
            trigger=f"Output validation on {run.run_id}",
            result=(
                f"Output contained {len(validation['failure_codes'])} validation failure(s)"
            ),
            related_object=incident.incident_id,
        )
        return {
            "incident": incident.as_dict(),
            "automation_run": automation.as_dict(),
        }

    def _action_payload(self, run: PipelineRun) -> dict[str, Any]:
        if run.pipeline_id == "finance-material-payment":
            output = run.model_output or {}
            return {
                "operation": "release_material_payment_batch",
                "target_case_id": run.case_id,
                "expected_version": run.source_snapshot["record_version"],
                "amount": output["recommended_release_amount"],
                "currency": output["currency"],
                "recommendation": output["recommendation"],
                "model_output_sha256": run.model["output_sha256"],
                "validation_sha256": _canonical_hash(run.validation),
            }
        return {
            "operation": "write_visit_summary_and_queue_secure_message",
            "target_case_id": run.case_id,
            "expected_version": run.source_snapshot["record_version"],
            "summary": deepcopy(run.model_output),
            "model_output_sha256": run.model["output_sha256"],
            "validation_sha256": _canonical_hash(run.validation),
        }

    def _propose_action(self, run: PipelineRun) -> None:
        if not run.validation or run.validation["status"] != "passed":
            raise PipelineWorkflowError("Only a validated model output can propose an action.")
        definition = self._definition(run.pipeline_id)
        payload = self._action_payload(run)
        payload_sha256 = _canonical_hash(payload)
        request = ActionRequest(
            agent_id=(
                "payment-operations-agent"
                if run.pipeline_id == "finance-material-payment"
                else "healthcare-visit-summary-agent"
            ),
            on_behalf_of=run.actor,
            tool=definition.tool,
            operation=definition.operation,
            resource=run.case_id,
            resource_classification="restricted",
            industry=definition.industry,
            use_case=definition.use_case,
            model_id=definition.model_id,
            model_version=definition.model_version,
            risk_attributes=(
                {
                    "amount": float(payload["amount"]),
                    "currency": payload["currency"],
                    "payload_sha256": payload_sha256,
                }
                if run.pipeline_id == "finance-material-payment"
                else {
                    "clinical_record_write": True,
                    "payload_sha256": payload_sha256,
                }
            ),
            parameters={"payload_sha256": payload_sha256},
        )
        governed = self.service.propose(request)
        run.action_payload = payload
        run.action_payload_sha256 = payload_sha256
        run.governed_action = governed.as_dict()
        self._complete_step(
            run,
            "action",
            "The validated action was sealed with a payload hash and evaluated by policy.",
        )
        self.service.audit_log.append(
            "pipeline.action_bound",
            run.run_id,
            {
                "pipeline_id": run.pipeline_id,
                "action_id": request.action_id,
                "action_payload_sha256": payload_sha256,
                "model_output_sha256": run.model["output_sha256"] if run.model else None,
                "runtime_event_id": (
                    run.runtime_event["event_id"] if run.runtime_event else None
                ),
                "content_stored": False,
            },
        )
        if governed.status.value == "waiting_approval":
            approval_step = self._step(run, "approval")
            approval_step.status = "waiting"
            approval_step.detail = (
                f"0 of {governed.decision.required_approvals} independent approvals recorded."
            )
            run.status = "waiting_approval"
            run.current_stage = "approval"
            return
        if governed.status.value == "denied":
            approval_step = self._step(run, "approval")
            approval_step.status = "skipped"
            self._skip_after(run, "approval")
            run.status = "denied"
            run.current_stage = None
            run.completed_at = now_iso()
            return

        # Both supplied industry pipelines are consequential.  An allow rule here
        # indicates a policy configuration error, so fail closed instead of using
        # a policy-only authorization.
        self._block(
            run,
            "The consequential action was not configured for human review.",
            "human_review_policy_missing",
            stage_id="approval",
        )

    def _reconcile(self, run: PipelineRun) -> None:
        if not run.execution or not run.action_payload:
            raise PipelineWorkflowError("Execution data is required for reconciliation.")
        after = run.execution["after_record"]
        if run.pipeline_id == "finance-material-payment":
            checks = [
                {
                    "check_id": "target_status_updated",
                    "passed": after["operational_status"] == "released_simulated",
                },
                {
                    "check_id": "amount_matches_approval",
                    "passed": float(after["release"]["amount"])
                    == float(run.action_payload["amount"]),
                },
                {
                    "check_id": "receipt_returned",
                    "passed": after["release"]["adapter_receipt"]
                    == run.execution["adapter_receipt"],
                },
            ]
        else:
            checks = [
                {
                    "check_id": "summary_signed",
                    "passed": after["operational_status"]
                    == "summary_signed_simulated",
                },
                {
                    "check_id": "summary_matches_approval",
                    "passed": _canonical_hash(
                        {
                            key: value
                            for key, value in after["signed_summary"].items()
                            if key not in {"signed_at", "adapter_receipt"}
                        }
                    )
                    == _canonical_hash(run.action_payload["summary"]),
                },
                {
                    "check_id": "secure_message_queued",
                    "passed": len(after["portal_queue"]) == 1
                    and after["portal_queue"][0]["status"] == "queued_simulated",
                },
            ]
        matched = all(check["passed"] for check in checks)
        run.reconciliation = {
            "status": "matched" if matched else "mismatch",
            "checks": checks,
            "reconciled_at": now_iso(),
            "before_version": run.execution["before_version"],
            "after_version": run.execution["after_version"],
        }
        step = self._step(run, "reconcile")
        step.status = "complete" if matched else "blocked"
        step.detail = (
            "The source-system outcome matches the exact approved action and receipt."
            if matched
            else "The source-system outcome does not match the approved action."
        )
        step.timestamp = run.reconciliation["reconciled_at"]
        self.service.audit_log.append(
            "pipeline.reconciled",
            run.run_id,
            {
                "pipeline_id": run.pipeline_id,
                "action_id": run.execution["action_id"],
                "adapter_receipt": run.execution["adapter_receipt"],
                "status": run.reconciliation["status"],
                "check_results": {
                    check["check_id"]: check["passed"] for check in checks
                },
            },
        )
        if not matched:
            raise PipelineWorkflowError("Execution reconciliation failed.")

    def _block(
        self,
        run: PipelineRun,
        detail: str,
        failure_code: str,
        *,
        stage_id: str | None = None,
        preserve_validation: bool = False,
    ) -> None:
        active_stage = stage_id or run.current_stage
        if active_stage:
            step = self._step(run, active_stage)
            step.status = "blocked"
            step.detail = detail
            step.timestamp = now_iso()
            self._skip_after(run, active_stage)
        if not preserve_validation:
            run.validation = run.validation or {
                "status": "blocked",
                "checks": [],
                "failure_codes": [failure_code],
            }
        run.status = "blocked"
        run.current_stage = None
        run.completed_at = now_iso()
        self.service.audit_log.append(
            "pipeline.blocked",
            run.run_id,
            {
                "pipeline_id": run.pipeline_id,
                "case_id": run.case_id,
                "stage_id": active_stage,
                "failure_code": failure_code,
                "provider_invoked": run.provider_invoked,
                "downstream_invoked": run.downstream_invoked,
            },
        )

    @staticmethod
    def _link_platform_objects(
        run: PipelineRun, result: dict[str, Any]
    ) -> None:
        incident = result.get("incident")
        automation = result.get("automation_run")
        if incident:
            incident_id = incident["incident_id"]
            if incident_id not in run.linked_incident_ids:
                run.linked_incident_ids.append(incident_id)
        if automation:
            automation_id = automation["run_id"]
            if automation_id not in run.linked_automation_run_ids:
                run.linked_automation_run_ids.append(automation_id)
