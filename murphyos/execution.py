"""End-to-end governed execution demonstration for StyrAI.

The workflow is intentionally local and deterministic. It exercises real policy,
approval and audit code while replacing the external model and email provider
with safe fixtures. No network call or real customer data is used.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from .models import ActionRequest
from .platform import GovernancePlatform, now_iso
from .service import GovernanceService


@dataclass
class ExecutionStep:
    step_id: str
    label: str
    detail: str
    status: str
    surface: str
    control_id: str | None = None
    timestamp: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionRun:
    run_id: str
    scenario: str
    title: str
    actor: str
    started_at: str
    status: str
    source_application: dict[str, Any]
    task: str
    steps: list[ExecutionStep] = field(default_factory=list)
    runtime_result: dict[str, Any] | None = None
    model_output: str | None = None
    governed_action: dict[str, Any] | None = None
    delivery: dict[str, Any] | None = None
    completed_at: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario": self.scenario,
            "title": self.title,
            "actor": self.actor,
            "started_at": self.started_at,
            "status": self.status,
            "source_application": self.source_application,
            "task": self.task,
            "steps": [step.as_dict() for step in self.steps],
            "runtime_result": self.runtime_result,
            "model_output": self.model_output,
            "governed_action": self.governed_action,
            "delivery": self.delivery,
            "completed_at": self.completed_at,
        }


class ExecutionDemo:
    """Coordinates a source task through model, policy, approval and tool execution."""

    CUSTOMER_CASE = {
        "application": "Client 360",
        "case_id": "CS-2841",
        "customer": "Anna Berg (fictional)",
        "email": "anna.berg@example.test",
        "account": "NO93 8601 1117 947",
        "classification": "Confidential",
        "request": "Explain which documents are still needed for the mortgage review.",
    }

    SOURCE_METADATA = {
        "application": "Client 360",
        "case_id": "CS-2841",
        "business_unit": "Retail Banking",
        "data_boundary": "Customer environment",
        "classification": "Confidential",
    }

    SCENARIOS = (
        {
            "scenario": "customer_reply",
            "name": "Governed customer reply",
            "promise": "Redact → model → approval → execute",
            "description": (
                "A service copilot drafts a customer reply using confidential case "
                "context, then proposes an external email for human approval."
            ),
        },
        {
            "scenario": "public_ai_paste",
            "name": "Blocked public-AI attempt",
            "promise": "Detect → block → contain → evidence",
            "description": (
                "An employee attempts to paste confidential context and a demo "
                "credential into an unapproved public AI service."
            ),
        },
    )

    SAFE_MODEL_OUTPUT = (
        "Hi Anna, we have reviewed your mortgage case. We still need your latest "
        "income documentation and confirmation of the deposit source. Please use "
        "the secure document portal; do not reply with documents by email."
    )

    def __init__(
        self, service: GovernanceService, platform: GovernancePlatform
    ) -> None:
        self.service = service
        self.platform = platform
        self.runs: dict[str, ExecutionRun] = {}
        self.latest_run_id: str | None = None

    @staticmethod
    def _step(
        step_id: str,
        label: str,
        detail: str,
        status: str,
        surface: str,
        control_id: str | None = None,
    ) -> ExecutionStep:
        return ExecutionStep(
            step_id=step_id,
            label=label,
            detail=detail,
            status=status,
            surface=surface,
            control_id=control_id,
            timestamp=now_iso() if status not in {"locked", "skipped"} else None,
        )

    @staticmethod
    def _receipt(prefix: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return prefix + hashlib.sha256(canonical).hexdigest()

    @classmethod
    def preview_case(cls) -> dict[str, Any]:
        return dict(cls.CUSTOMER_CASE)

    @classmethod
    def source_metadata(cls) -> dict[str, Any]:
        return dict(cls.SOURCE_METADATA)

    def state(self) -> dict[str, Any]:
        latest = self.runs.get(self.latest_run_id or "")
        return {
            "mode": "local_deterministic_demo",
            "external_model_connected": False,
            "external_tool_connected": False,
            "governance_path_live": True,
            "scenarios": [dict(item) for item in self.SCENARIOS],
            "preview_case": self.preview_case(),
            "latest_run": latest.as_dict() if latest else None,
            "runs_completed": sum(
                run.status in {"executed", "blocked", "denied"}
                for run in self.runs.values()
            ),
        }

    def start(self, scenario: str) -> dict[str, Any]:
        if scenario not in {item["scenario"] for item in self.SCENARIOS}:
            raise ValueError("Unknown execution scenario.")
        if scenario == "customer_reply":
            return self._start_customer_reply().as_dict()
        return self._start_public_ai_attempt().as_dict()

    def _start_customer_reply(self) -> ExecutionRun:
        run_id = "EXEC-" + uuid4().hex[:8].upper()
        raw_prompt = (
            "Customer anna.berg@example.test, account NO93 8601 1117 947, "
            "asks which mortgage documents remain. This is confidential."
        )
        runtime = self.platform.simulate_model_call(
            {
                "asset_id": "agent-client-service",
                "actor": "advisor-demo",
                "classification": "confidential",
                "prompt": raw_prompt,
            }
        )
        event = runtime["event"]
        if event["decision"] not in {"allowed", "allow_with_redaction"}:
            raise RuntimeError("The approved model route was unexpectedly blocked.")

        request = ActionRequest(
            agent_id="client-service-copilot",
            on_behalf_of="advisor-demo",
            tool="email",
            operation="send_external",
            resource="anna.berg@example.test",
            resource_classification="internal",
            industry="financial_services",
            use_case="customer_communication",
            model_id="enterprise-language-model",
            model_version="2026-08",
            parameters={"content": self.SAFE_MODEL_OUTPUT},
        )
        governed = self.service.propose(request)
        self.service.audit_log.append(
            "model.draft_generated",
            run_id,
            {
                "runtime_event_id": event["event_id"],
                "model_id": request.model_id,
                "model_version": request.model_version,
                "input_hash": event["prompt_hash"],
                "output_hash": hashlib.sha256(
                    self.SAFE_MODEL_OUTPUT.encode("utf-8")
                ).hexdigest(),
                "adapter": "local-deterministic-model",
                "content_stored": False,
            },
        )
        run = ExecutionRun(
            run_id=run_id,
            scenario="customer_reply",
            title="Governed customer reply",
            actor="advisor-demo",
            started_at=now_iso(),
            status="waiting_approval",
            source_application=self.source_metadata(),
            task="Draft and send a reply explaining the outstanding documents.",
            runtime_result={
                "event_id": event["event_id"],
                "decision": event["decision"],
                "reason": event["reason"],
                "effective_classification": event["effective_classification"],
                "detected_data_types": event["detected_data_types"],
                "controls_applied": event["controls_applied"],
                "destination": event["destination"],
                "redaction_count": event["redaction_count"],
                "provider_payload": event["redacted_preview"],
                "prompt_hash": event["prompt_hash"],
                "raw_input_stored": runtime["raw_input_stored"],
            },
            model_output=self.SAFE_MODEL_OUTPUT,
            governed_action=governed.as_dict(),
            steps=[
                self._step("source", "Task requested", "Client 360 supplied the case context to the copilot.", "complete", "source"),
                self._step("intercept", "Input intercepted", f"StyrAI classified the call as confidential and detected {len(event['detected_data_types'])} sensitive pattern types.", "complete", "overlay", "DATA-OUT-01"),
                self._step("redact", "Provider payload minimised", f"{event['redaction_count']} sensitive values were removed before the approved zero-retention route.", "complete", "overlay", "DATA-OUT-01"),
                self._step("model", "Model executed", "The deterministic local model fixture produced a customer-safe draft through the approved passport.", "complete", "model", "MODEL-USE-02"),
                self._step("action", "External email proposed", "The copilot requested the email tool; the action is bound to the exact model and policy version.", "complete", "tool", "MODEL-USE-02"),
                self._step("approval", "Human approval required", "External communication is paused for an independent reviewer and rationale.", "waiting", "overlay", "HUMAN-01"),
                self._step("execute", "Tool execution locked", "No email can be delivered until StyrAI issues an authorisation receipt.", "locked", "tool", "HUMAN-01"),
            ],
        )
        self.runs[run.run_id] = run
        self.latest_run_id = run.run_id
        self.service.audit_log.append(
            "execution.started",
            run.run_id,
            {
                "scenario": run.scenario,
                "actor": run.actor,
                "runtime_event_id": event["event_id"],
                "action_id": request.action_id,
                "prompt_hash": event["prompt_hash"],
                "raw_input_stored": False,
            },
        )
        return run

    def _start_public_ai_attempt(self) -> ExecutionRun:
        run_id = "EXEC-" + uuid4().hex[:8].upper()
        raw_prompt = (
            "Paste customer account NO93 8601 1117 947 into a public assistant. "
            "api_key=fictional-demo-secret. This is confidential."
        )
        runtime = self.platform.simulate_model_call(
            {
                "asset_id": "shadow-public-ai",
                "actor": "advisor-demo",
                "classification": "confidential",
                "prompt": raw_prompt,
            }
        )
        event = runtime["event"]
        incident = runtime["incident"]
        run = ExecutionRun(
            run_id=run_id,
            scenario="public_ai_paste",
            title="Blocked public-AI attempt",
            actor="advisor-demo",
            started_at=now_iso(),
            completed_at=now_iso(),
            status="blocked",
            source_application={
                **self.source_metadata(),
                "application": "Unapproved public AI tab",
            },
            task="Paste confidential customer context into an unapproved assistant.",
            runtime_result={
                "event_id": event["event_id"],
                "decision": event["decision"],
                "reason": event["reason"],
                "effective_classification": event["effective_classification"],
                "detected_data_types": event["detected_data_types"],
                "controls_applied": event["controls_applied"],
                "destination": event["destination"],
                "redaction_count": event["redaction_count"],
                "provider_payload": None,
                "prompt_hash": event["prompt_hash"],
                "raw_input_stored": runtime["raw_input_stored"],
                "incident_id": incident["incident_id"] if incident else None,
                "automation_run_id": (
                    runtime["automation_run"]["run_id"]
                    if runtime.get("automation_run")
                    else None
                ),
            },
            steps=[
                self._step("source", "Paste attempted", "The employee attempted to use confidential context in an unapproved AI tab.", "complete", "source"),
                self._step("intercept", "Input intercepted", "StyrAI detected restricted credential material and confidential account context.", "complete", "overlay", "DATA-OUT-01"),
                self._step("block", "Transmission blocked", event["reason"], "blocked", "overlay", "DATA-OUT-01"),
                self._step("incident", "Containment automated", f"Incident {incident['incident_id']} was opened and the destination remained blocked.", "complete", "platform", "INC-01"),
                self._step("model", "Model not called", "No payload crossed the customer trust boundary.", "skipped", "model"),
                self._step("execute", "No tool execution", "No downstream action or approval was created.", "skipped", "tool"),
            ],
        )
        self.runs[run.run_id] = run
        self.latest_run_id = run.run_id
        self.service.audit_log.append(
            "execution.blocked",
            run.run_id,
            {
                "scenario": run.scenario,
                "runtime_event_id": event["event_id"],
                "incident_id": incident["incident_id"] if incident else None,
                "prompt_hash": event["prompt_hash"],
                "raw_input_stored": False,
            },
        )
        return run

    def decide(
        self,
        run_id: str,
        *,
        approver_id: str,
        approved: bool,
        rationale: str,
    ) -> dict[str, Any]:
        run = self.runs.get(run_id)
        if run is None:
            raise ValueError("Unknown execution run.")
        if run.status != "waiting_approval" or not run.governed_action:
            raise ValueError("Execution is not waiting for approval.")
        if not approver_id.strip():
            raise ValueError("An approver is required.")
        action_id = run.governed_action["action"]["action_id"]
        governed = self.service.decide_approval(
            action_id=action_id,
            approver_id=approver_id.strip(),
            approved=approved,
            rationale=rationale,
        )
        run.governed_action = governed.as_dict()
        approval_step = next(step for step in run.steps if step.step_id == "approval")
        execute_step = next(step for step in run.steps if step.step_id == "execute")
        approval_step.timestamp = now_iso()

        if not approved:
            run.status = "denied"
            run.completed_at = now_iso()
            approval_step.status = "denied"
            approval_step.detail = "The reviewer denied the external communication."
            execute_step.status = "skipped"
            execute_step.detail = "The email tool remained locked; nothing was delivered."
            return run.as_dict()

        if governed.status.value != "authorized":
            approval_step.status = "waiting"
            approval_step.detail = "Another independent approval is still required."
            return run.as_dict()

        approval_step.status = "complete"
        approval_step.detail = (
            f"{approver_id.strip()} approved with a recorded rationale."
        )
        execute_step.status = "ready"
        execute_step.detail = (
            "Authorisation receipt issued. The local email adapter is ready to "
            "execute the exact approved action."
        )
        run.status = "authorized"
        return run.as_dict()

    def execute(self, run_id: str) -> dict[str, Any]:
        run = self.runs.get(run_id)
        if run is None:
            raise ValueError("Unknown execution run.")
        if run.status == "executed" and run.delivery:
            return run.as_dict()
        if run.status != "authorized" or not run.governed_action:
            raise ValueError("Execution requires an authorised action.")
        governed = self.service.assert_authorized(
            run.governed_action["action"]["action_id"]
        )
        recipient = governed.request.resource
        recipient_domain = recipient.rsplit("@", 1)[-1]
        if recipient_domain != "example.test" and not recipient_domain.endswith(
            ".example.test"
        ):
            raise ValueError(
                "The demonstration connector only accepts example.test recipients."
            )
        action_id = governed.request.action_id
        execute_step = next(step for step in run.steps if step.step_id == "execute")
        execute_step.status = "complete"
        execute_step.timestamp = now_iso()
        execute_step.detail = (
            "The local email adapter accepted the authorised draft and returned a "
            "simulated delivery receipt."
        )
        delivery_claims = {
            "run_id": run.run_id,
            "action_id": action_id,
            "authorization_receipt": governed.authorization_receipt,
            "adapter": "local-demo-email-adapter",
            "outcome": "simulated_delivered",
            "content_sha256": hashlib.sha256(
                (run.model_output or "").encode("utf-8")
            ).hexdigest(),
        }
        delivery_receipt = self._receipt("styrai_delivery_v1_", delivery_claims)
        run.delivery = {
            **delivery_claims,
            "recipient": "anna.berg@example.test",
            "completed_at": now_iso(),
            "delivery_receipt": delivery_receipt,
            "external_side_effect": False,
        }
        run.status = "executed"
        run.completed_at = run.delivery["completed_at"]
        self.service.audit_log.append(
            "tool.execution_simulated",
            action_id,
            {
                **delivery_claims,
                "delivery_receipt": delivery_receipt,
                "content_stored": False,
                "external_side_effect": False,
            },
        )
        return run.as_dict()

    def evidence(self, run_id: str) -> dict[str, Any]:
        run = self.runs.get(run_id)
        if run is None:
            raise ValueError("Unknown execution run.")
        runtime_event_id = (
            run.runtime_result.get("event_id") if run.runtime_result else None
        )
        action_id = (
            run.governed_action["action"]["action_id"]
            if run.governed_action
            else None
        )
        incident_id = (
            run.runtime_result.get("incident_id") if run.runtime_result else None
        )
        automation_run_id = (
            run.runtime_result.get("automation_run_id")
            if run.runtime_result
            else None
        )
        identifiers = {
            run.run_id,
            runtime_event_id,
            action_id,
            incident_id,
            automation_run_id,
        }
        records = [
            record
            for record in self.service.audit_log.records()
            if record["action_id"] in identifiers
            or record.get("payload", {}).get("runtime_event_id") == runtime_event_id
            or record.get("payload", {}).get("action_id") == action_id
        ]
        run_evidence = deepcopy(run.as_dict())
        run_evidence["model_output"] = None
        if run_evidence.get("runtime_result"):
            run_evidence["runtime_result"]["provider_payload"] = None
        return {
            "schema": "styrai.execution-evidence.v1",
            "run": run_evidence,
            "audit_records": records,
            "audit_chain_valid": self.service.audit_log.verify(),
            "data_statement": (
                "The source surface uses fictional demo data. Governance evidence "
                "contains hashes and metadata, not the raw model input or email body."
            ),
            "disclaimer": (
                "The external model and email delivery are local deterministic "
                "fixtures; the policy, approval and audit path executes live."
            ),
        }
