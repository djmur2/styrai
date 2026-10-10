"""Local customer-demonstration server for StyrAI."""

from __future__ import annotations

import argparse
import json
import threading
import time
import webbrowser
from collections.abc import Sequence
from email import policy as email_policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from .ai_governance import AIGovernanceControlPlane
from .audit import AuditIntegrityError, HashChainedAuditLog
from .dataset_governance import DatasetGovernanceEngine
from .demo import demo_policy, demo_registry
from .execution import ExecutionDemo
from .industry_pipelines import PipelineService
from .models import ActionRequest
from .policy import PolicyEngine
from .platform import GovernancePlatform
from .service import GovernanceService, GovernanceWorkflowError


STYRAI_BUILD = "upload-governance-v1"
STYRAI_CAPABILITIES = (
    "dataset-governance-run-v1",
    "internal-policy-controls-v1",
)


class DemoApplication:
    """In-memory workflow state backed by a local audit-evidence file."""

    def __init__(self, audit_path: Path) -> None:
        self.audit_path = audit_path
        self.lock = threading.RLock()
        self.service: GovernanceService
        self.platform: GovernancePlatform
        self.execution: ExecutionDemo
        self.pipelines: PipelineService
        self.reset()

    def reset(self) -> dict[str, Any]:
        with self.lock:
            if self.audit_path.exists():
                self.audit_path.unlink()
            self.service = GovernanceService(
                PolicyEngine(demo_policy()),
                HashChainedAuditLog(self.audit_path),
                registry=demo_registry(),
            )
            self._seed()
            self.platform = GovernancePlatform(self.service.audit_log)
            self.ai_governance = AIGovernanceControlPlane(self.service.audit_log)
            self.dataset_governance = DatasetGovernanceEngine(self.service.audit_log)
            self.execution = ExecutionDemo(self.service, self.platform)
            self.pipelines = PipelineService(self.service, self.platform)
            return self.state()

    def _seed(self) -> None:
        for scenario in (
            "document_read",
            "external_email_restricted",
            "material_payment",
        ):
            self.service.propose(self._request_for_scenario(scenario))

    @staticmethod
    def _request_for_scenario(
        scenario: str, amount: float | None = None
    ) -> ActionRequest:
        if scenario == "document_read":
            return ActionRequest(
                agent_id="client-service-copilot",
                on_behalf_of="advisor-1042",
                tool="documents",
                operation="read",
                resource="customer-service-procedure-184",
                resource_classification="internal",
                industry="financial_services",
                use_case="customer_service",
                model_id="enterprise-language-model",
                model_version="2026-08",
            )
        if scenario == "external_email":
            return ActionRequest(
                agent_id="client-service-copilot",
                on_behalf_of="advisor-1042",
                tool="email",
                operation="send_external",
                resource="customer@example.test",
                resource_classification="internal",
                industry="financial_services",
                use_case="customer_communication",
                model_id="enterprise-language-model",
                model_version="2026-08",
            )
        if scenario == "external_email_restricted":
            return ActionRequest(
                agent_id="client-service-copilot",
                on_behalf_of="advisor-1042",
                tool="email",
                operation="send_external",
                resource="external-recipient@example.test",
                resource_classification="restricted",
                industry="financial_services",
                use_case="customer_communication",
                model_id="enterprise-language-model",
                model_version="2026-08",
            )
        if scenario in {"material_payment", "standard_payment"}:
            payment_amount = amount if amount is not None else (
                250_000 if scenario == "material_payment" else 25_000
            )
            return ActionRequest(
                agent_id="payment-operations-agent",
                on_behalf_of="payments-operator-19",
                tool="payments",
                operation="release",
                resource="payment-batch-demo",
                resource_classification="restricted",
                industry="financial_services",
                use_case="payment_operations",
                model_id="approved-operations-model",
                model_version="2026-08-15",
                risk_attributes={"amount": payment_amount, "currency": "NOK"},
            )
        raise ValueError("Unknown demonstration scenario.")

    def propose(self, payload: dict[str, Any]) -> dict[str, Any]:
        scenario = str(payload.get("scenario", ""))
        raw_amount = payload.get("amount")
        amount: float | None = None
        if raw_amount is not None and raw_amount != "":
            amount = float(raw_amount)
            if amount <= 0:
                raise ValueError("Payment amount must be positive.")
        with self.lock:
            governed = self.service.propose(
                self._request_for_scenario(scenario, amount=amount)
            )
            return governed.as_dict()

    def approve(self, action_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        approver_id = str(payload.get("approver_id", "")).strip()
        rationale = str(payload.get("rationale", "")).strip()
        approved = bool(payload.get("approved", True))
        if not approver_id:
            raise ValueError("Approver is required.")
        with self.lock:
            return self.service.decide_approval(
                action_id=action_id,
                approver_id=approver_id,
                approved=approved,
                rationale=rationale,
            ).as_dict()

    def state(self) -> dict[str, Any]:
        with self.lock:
            actions = [item.as_dict() for item in reversed(self.service.list_actions())]
            records = list(reversed(self.service.audit_log.records()))
            try:
                integrity_valid = self.service.audit_log.verify()
            except AuditIntegrityError:
                integrity_valid = False
            return {
                "policy_version": self.service.engine.policy_set.version,
                "actions": actions,
                "audit": {
                    "valid": integrity_valid,
                    "record_count": len(records),
                    "recent_records": records[:8],
                },
            }

    def evidence(self, action_id: str) -> dict[str, Any]:
        with self.lock:
            action = self.service.get(action_id).as_dict()
            records = [
                record
                for record in self.service.audit_log.records()
                if record["action_id"] == action_id
            ]
            return {
                "schema": "styrai.evidence.v1",
                "generated_for_demonstration": True,
                "action": action,
                "audit_records": records,
                "audit_chain_valid": self.service.audit_log.verify(),
                "disclaimer": (
                    "Technical demonstration evidence; not a certification of "
                    "regulatory compliance."
                ),
            }

    def platform_state(self) -> dict[str, Any]:
        with self.lock:
            return self.platform.state()

    def simulate_model_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.platform.simulate_model_call(payload)

    def simulate_health_breach(
        self, asset_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            return self.platform.simulate_health_breach(
                asset_id, str(payload.get("breach", "quality"))
            )

    def simulate_version_change(self, asset_id: str) -> dict[str, Any]:
        with self.lock:
            return self.platform.simulate_version_change(asset_id)

    def run_automation(self, rule_id: str) -> dict[str, Any]:
        with self.lock:
            return self.platform.run_automation(rule_id)

    def resolve_incident(self, incident_id: str) -> dict[str, Any]:
        with self.lock:
            return self.platform.resolve_incident(incident_id)

    def evidence_pack(self, pack_id: str) -> dict[str, Any]:
        with self.lock:
            return self.platform.evidence_pack(pack_id)

    def execution_state(self) -> dict[str, Any]:
        with self.lock:
            return self.execution.state()

    def start_execution(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.execution.start(str(payload.get("scenario", "customer_reply")))

    def decide_execution(
        self, run_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            return self.execution.decide(
                run_id,
                approver_id=str(payload.get("approver_id", "")),
                approved=bool(payload.get("approved", True)),
                rationale=str(payload.get("rationale", "")),
            )

    def execute_run(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            return self.execution.execute(run_id)

    def execution_evidence(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            return self.execution.evidence(run_id)

    def pipeline_state(self) -> dict[str, Any]:
        with self.lock:
            return self.pipelines.state()

    def pipeline_cases(self, pipeline_id: str) -> list[dict[str, Any]]:
        with self.lock:
            return self.pipelines.cases(pipeline_id)

    def pipeline_case_record(
        self, pipeline_id: str, case_id: str
    ) -> dict[str, Any]:
        with self.lock:
            return self.pipelines.case_record(pipeline_id, case_id)

    def start_pipeline(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.pipelines.start(payload)

    def advance_pipeline(
        self, run_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            return self.pipelines.advance(
                run_id, until=str(payload.get("until", "next"))
            )

    def decide_pipeline(
        self, run_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            return self.pipelines.decide(
                run_id,
                approver_id=str(payload.get("approver_id", "")).strip(),
                approved=bool(payload.get("approved", True)),
                rationale=str(payload.get("rationale", "")).strip(),
            )

    def execute_pipeline(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            return self.pipelines.execute(run_id)

    def reconcile_pipeline(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            return self.pipelines.reconcile(run_id)

    def inject_pipeline(
        self, run_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            return self.pipelines.inject(run_id, str(payload.get("kind", "drift")))

    def pipeline_evidence(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            return self.pipelines.evidence(run_id)

    def ai_governance_state(self) -> dict[str, Any]:
        with self.lock:
            return self.ai_governance.state()

    def inspect_ai_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.ai_governance.inspect_prompt(payload)

    def assess_ai_model(self, model_id: str) -> dict[str, Any]:
        with self.lock:
            return self.ai_governance.assess_model(model_id)

    def monitor_ai_model(
        self, model_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            return self.ai_governance.record_monitoring_event(model_id, payload)

    def observe_ai_model_version(
        self, model_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            return self.ai_governance.observe_model_version(model_id, payload)

    def resolve_ai_finding(
        self, finding_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            return self.ai_governance.resolve_finding(finding_id, payload)

    def ai_governance_evidence(self, object_id: str) -> dict[str, Any]:
        with self.lock:
            try:
                return self.ai_governance.evidence(object_id)
            except ValueError as ai_governance_error:
                try:
                    return self.dataset_governance.evidence(object_id)
                except ValueError:
                    raise ai_governance_error

    def regulation_library(self) -> dict[str, Any]:
        with self.lock:
            return self.dataset_governance.regulations()

    def dataset_schema(self) -> dict[str, Any]:
        with self.lock:
            return self.dataset_governance.dataset_schema()

    def internal_policies(self) -> list[dict[str, Any]]:
        with self.lock:
            return self.dataset_governance.list_policies()

    def create_internal_policy_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.dataset_governance.create_policy_draft(payload)

    def activate_internal_policy(
        self, policy_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.lock:
            return self.dataset_governance.activate_policy(policy_id, payload)

    def dataset_runs(self) -> list[dict[str, Any]]:
        with self.lock:
            return self.dataset_governance.list_runs()

    def dataset_run(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            return self.dataset_governance.get_run(run_id)

    def run_governance_dataset(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            return self.dataset_governance.run_dataset(payload)


class StyrAIRequestHandler(BaseHTTPRequestHandler):
    application: DemoApplication
    web_root = Path(__file__).resolve().parent.parent / "web"

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        path = urlparse(self.path).path
        upload_route = path in {
            "/api/governance/dataset-runs",
            "/api/governance/policies/drafts",
        }
        maximum = 1_100_000 if upload_route else 64_000
        if length > maximum:
            raise ValueError("Request is too large.")
        raw = self.rfile.read(length) if length else b"{}"
        content_type = self.headers.get("Content-Type", "application/json")
        if content_type.lower().startswith("multipart/form-data"):
            message = BytesParser(policy=email_policy.default).parsebytes(
                (
                    f"Content-Type: {content_type}\r\n"
                    "MIME-Version: 1.0\r\n\r\n"
                ).encode("utf-8")
                + raw
            )
            if not message.is_multipart():
                raise ValueError("Malformed multipart request.")
            payload: dict[str, Any] = {}
            file_seen = False
            for part in message.iter_parts():
                field_name = part.get_param("name", header="content-disposition")
                if not field_name:
                    continue
                body = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                try:
                    value = body.decode(charset)
                except (LookupError, UnicodeDecodeError) as exc:
                    raise ValueError("Uploaded content must be UTF-8 text.") from exc
                filename = part.get_filename()
                if filename is not None:
                    if file_seen:
                        raise ValueError("Upload exactly one CSV, JSON, or text file.")
                    file_seen = True
                    payload["filename"] = Path(filename).name
                    payload["content"] = value
                else:
                    payload[str(field_name)] = value
            if isinstance(payload.get("policy_ids"), str):
                raw_policy_ids = str(payload["policy_ids"]).strip()
                if raw_policy_ids:
                    try:
                        parsed_ids = json.loads(raw_policy_ids)
                    except json.JSONDecodeError:
                        parsed_ids = [
                            item.strip()
                            for item in raw_policy_ids.split(",")
                            if item.strip()
                        ]
                    payload["policy_ids"] = parsed_ids
            return payload
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object.")
        return payload

    def _send_static(self, name: str, content_type: str) -> None:
        target = self.web_root / name
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        encoded = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/":
                self._send_static("index.html", "text/html; charset=utf-8")
            elif path == "/api/health":
                self._send_json(
                    {
                        "status": "ok",
                        "product": "StyrAI",
                        "mode": "synthetic-demo",
                        "build": STYRAI_BUILD,
                        "capabilities": list(STYRAI_CAPABILITIES),
                    }
                )
            elif path == "/app.js":
                self._send_static("app.js", "text/javascript; charset=utf-8")
            elif path == "/styles.css":
                self._send_static("styles.css", "text/css; charset=utf-8")
            elif path == "/api/state":
                self._send_json(self.application.state())
            elif path == "/api/platform":
                self._send_json(self.application.platform_state())
            elif path == "/api/governance":
                self._send_json(self.application.ai_governance_state())
            elif path == "/api/governance/models":
                self._send_json(self.application.ai_governance_state()["models"])
            elif path == "/api/governance/assessments":
                self._send_json(
                    self.application.ai_governance_state()["assessments"]
                )
            elif path == "/api/governance/findings":
                self._send_json(self.application.ai_governance_state()["findings"])
            elif path == "/api/governance/events":
                self._send_json(
                    self.application.ai_governance_state()["runtime_events"]
                )
            elif path == "/api/governance/incidents":
                self._send_json(self.application.ai_governance_state()["incidents"])
            elif path == "/api/governance/regulations":
                self._send_json(self.application.regulation_library())
            elif path == "/api/governance/dataset-schema":
                self._send_json(self.application.dataset_schema())
            elif path == "/api/governance/policies":
                self._send_json(self.application.internal_policies())
            elif path == "/api/governance/dataset-runs":
                self._send_json(self.application.dataset_runs())
            elif path.startswith("/api/governance/dataset-runs/"):
                run_id = path.removeprefix("/api/governance/dataset-runs/")
                self._send_json(self.application.dataset_run(run_id))
            elif path.startswith("/api/governance/evidence/"):
                object_id = path.removeprefix("/api/governance/evidence/")
                self._send_json(
                    self.application.ai_governance_evidence(object_id)
                )
            elif path == "/api/execution":
                self._send_json(self.application.execution_state())
            elif path == "/api/pipelines":
                self._send_json(self.application.pipeline_state())
            elif path.startswith("/api/pipeline-runs/") and path.endswith("/evidence"):
                run_id = path.removeprefix("/api/pipeline-runs/").removesuffix(
                    "/evidence"
                )
                self._send_json(self.application.pipeline_evidence(run_id))
            elif path.startswith("/api/pipelines/") and path.endswith("/cases"):
                pipeline_id = path.removeprefix("/api/pipelines/").removesuffix(
                    "/cases"
                )
                self._send_json(self.application.pipeline_cases(pipeline_id))
            elif path.startswith("/api/demo-records/"):
                record_path = path.removeprefix("/api/demo-records/").split("/", 1)
                if len(record_path) != 2:
                    raise ValueError("A pipeline and synthetic case are required.")
                self._send_json(
                    self.application.pipeline_case_record(
                        record_path[0], record_path[1]
                    )
                )
            elif path.startswith("/api/executions/") and path.endswith("/evidence"):
                run_id = path.removeprefix("/api/executions/").removesuffix(
                    "/evidence"
                )
                self._send_json(self.application.execution_evidence(run_id))
            elif path.startswith("/api/packs/"):
                pack_id = path.removeprefix("/api/packs/")
                self._send_json(self.application.evidence_pack(pack_id))
            elif path.startswith("/api/evidence/"):
                action_id = path.removeprefix("/api/evidence/")
                self._send_json(self.application.evidence(action_id))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (GovernanceWorkflowError, ValueError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
            if path == "/api/actions":
                self._send_json(
                    self.application.propose(payload), HTTPStatus.CREATED
                )
            elif path == "/api/reset":
                self._send_json(self.application.reset())
            elif path == "/api/platform/reset":
                self.application.reset()
                self._send_json(self.application.platform_state())
            elif path == "/api/governance/reset":
                self.application.reset()
                self._send_json(self.application.ai_governance_state())
            elif path == "/api/governance/inspect":
                self._send_json(self.application.inspect_ai_prompt(payload))
            elif path == "/api/governance/policies/drafts":
                self._send_json(
                    self.application.create_internal_policy_draft(payload),
                    HTTPStatus.CREATED,
                )
            elif path.startswith("/api/governance/policies/") and path.endswith(
                "/activate"
            ):
                policy_id = path.removeprefix(
                    "/api/governance/policies/"
                ).removesuffix("/activate")
                self._send_json(
                    self.application.activate_internal_policy(policy_id, payload)
                )
            elif path == "/api/governance/dataset-runs":
                self._send_json(
                    self.application.run_governance_dataset(payload),
                    HTTPStatus.CREATED,
                )
            elif path.startswith("/api/governance/models/") and path.endswith(
                "/assess"
            ):
                model_id = path.removeprefix("/api/governance/models/").removesuffix(
                    "/assess"
                )
                self._send_json(self.application.assess_ai_model(model_id))
            elif path.startswith("/api/governance/models/") and path.endswith(
                "/monitor"
            ):
                model_id = path.removeprefix("/api/governance/models/").removesuffix(
                    "/monitor"
                )
                self._send_json(
                    self.application.monitor_ai_model(model_id, payload)
                )
            elif path.startswith("/api/governance/models/") and path.endswith(
                "/observe-version"
            ):
                model_id = path.removeprefix("/api/governance/models/").removesuffix(
                    "/observe-version"
                )
                self._send_json(
                    self.application.observe_ai_model_version(model_id, payload)
                )
            elif path.startswith("/api/governance/findings/") and path.endswith(
                "/resolve"
            ):
                finding_id = path.removeprefix(
                    "/api/governance/findings/"
                ).removesuffix("/resolve")
                self._send_json(
                    self.application.resolve_ai_finding(finding_id, payload)
                )
            elif path == "/api/simulate/call":
                self._send_json(self.application.simulate_model_call(payload))
            elif path == "/api/executions":
                self._send_json(
                    self.application.start_execution(payload), HTTPStatus.CREATED
                )
            elif path == "/api/pipeline-runs":
                self._send_json(
                    self.application.start_pipeline(payload), HTTPStatus.CREATED
                )
            elif path.startswith("/api/pipeline-runs/") and path.endswith("/advance"):
                run_id = path.removeprefix("/api/pipeline-runs/").removesuffix(
                    "/advance"
                )
                self._send_json(self.application.advance_pipeline(run_id, payload))
            elif path.startswith("/api/pipeline-runs/") and path.endswith("/decision"):
                run_id = path.removeprefix("/api/pipeline-runs/").removesuffix(
                    "/decision"
                )
                self._send_json(self.application.decide_pipeline(run_id, payload))
            elif path.startswith("/api/pipeline-runs/") and path.endswith("/execute"):
                run_id = path.removeprefix("/api/pipeline-runs/").removesuffix(
                    "/execute"
                )
                self._send_json(self.application.execute_pipeline(run_id))
            elif path.startswith("/api/pipeline-runs/") and path.endswith("/reconcile"):
                run_id = path.removeprefix("/api/pipeline-runs/").removesuffix(
                    "/reconcile"
                )
                self._send_json(self.application.reconcile_pipeline(run_id))
            elif path.startswith("/api/pipeline-runs/") and path.endswith("/inject"):
                run_id = path.removeprefix("/api/pipeline-runs/").removesuffix(
                    "/inject"
                )
                self._send_json(self.application.inject_pipeline(run_id, payload))
            elif path.startswith("/api/executions/") and path.endswith("/decision"):
                run_id = path.removeprefix("/api/executions/").removesuffix(
                    "/decision"
                )
                self._send_json(self.application.decide_execution(run_id, payload))
            elif path.startswith("/api/executions/") and path.endswith("/execute"):
                run_id = path.removeprefix("/api/executions/").removesuffix(
                    "/execute"
                )
                self._send_json(self.application.execute_run(run_id))
            elif path.startswith("/api/models/") and path.endswith("/health-breach"):
                asset_id = path.removeprefix("/api/models/").removesuffix(
                    "/health-breach"
                )
                self._send_json(
                    self.application.simulate_health_breach(asset_id, payload)
                )
            elif path.startswith("/api/models/") and path.endswith("/version-change"):
                asset_id = path.removeprefix("/api/models/").removesuffix(
                    "/version-change"
                )
                self._send_json(self.application.simulate_version_change(asset_id))
            elif path.startswith("/api/automations/") and path.endswith("/run"):
                rule_id = path.removeprefix("/api/automations/").removesuffix("/run")
                self._send_json(self.application.run_automation(rule_id))
            elif path.startswith("/api/incidents/") and path.endswith("/resolve"):
                incident_id = path.removeprefix("/api/incidents/").removesuffix(
                    "/resolve"
                )
                self._send_json(self.application.resolve_incident(incident_id))
            elif path.startswith("/api/actions/") and path.endswith("/approval"):
                action_id = path.removeprefix("/api/actions/").removesuffix(
                    "/approval"
                )
                self._send_json(self.application.approve(action_id, payload))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (GovernanceWorkflowError, ValueError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def _browser_urls(host: str, port: int) -> tuple[str, str]:
    base_url = f"http://{host}:{port}"
    return f"{base_url}/api/health", f"{base_url}/?presentation=1"


def _open_browser_when_ready(
    health_url: str,
    presentation_url: str,
    timeout_seconds: float = 8.0,
) -> None:
    """Open presenter mode only after the HTTP loop answers its health check."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=0.5) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("status") == "ok" and payload.get("product") == "StyrAI":
                webbrowser.open(presentation_url)
                return
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError):
            time.sleep(0.1)
    print(
        "The demo is running, but the browser could not be opened automatically.\n"
        f"Open this address manually: {presentation_url}",
        flush=True,
    )


def serve(
    host: str,
    port: int,
    audit_path: Path,
    *,
    open_browser: bool = False,
) -> None:
    application = DemoApplication(audit_path)
    handler = type(
        "ConfiguredStyrAIHandler",
        (StyrAIRequestHandler,),
        {"application": application},
    )
    server = ThreadingHTTPServer((host, port), handler)
    health_url, presentation_url = _browser_urls(host, port)
    print(f"StyrAI demonstration available at http://{host}:{port}", flush=True)
    if open_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(health_url, presentation_url),
            name="styrai-browser-launcher",
            daemon=True,
        ).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--audit-path",
        type=Path,
        default=Path("work/web-demo-audit.jsonl"),
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the demonstration in presenter mode after the server is ready.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    serve(
        args.host,
        args.port,
        args.audit_path,
        open_browser=args.open_browser,
    )


if __name__ == "__main__":
    main()
