"""Local customer-demonstration server for StyrAI."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import secrets
import threading
import time
import webbrowser
from collections.abc import Mapping, Sequence
from email import policy as email_policy
from email.parser import BytesParser
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from .ai_governance import AIGovernanceControlPlane
from .auth import (
    SESSION_TTL_SECONDS,
    create_session_token,
    load_auth_users,
    load_session_secret,
    verify_password,
    verify_session_token,
)
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
        self._initialize()

    def _initialize(self) -> dict[str, Any]:
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

    def reset(self) -> dict[str, Any]:
        with self.lock:
            self.service.audit_log.rotate()
            return self._initialize()

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
        demonstration_approver_id = str(
            payload.get("demonstration_approver_id")
            or payload.get("demo_approver_id")
            or ""
        ).strip()
        approver_id = str(
            payload.get("approver_id") or demonstration_approver_id
        ).strip()
        with self.lock:
            return self.pipelines.decide(
                run_id,
                approver_id=approver_id,
                approved=bool(payload.get("approved", True)),
                rationale=str(payload.get("rationale", "")).strip(),
                demonstration_approver_id=demonstration_approver_id or None,
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
    auth_users: Mapping[str, str] = {}
    session_secret: bytes | None = None
    active_sessions: dict[str, int] = {}
    active_sessions_lock = threading.Lock()
    authenticated_username: str | None = None
    web_root = Path(__file__).resolve().parent.parent / "web"

    SESSION_COOKIE = "__Host-styrai_session"
    LOGIN_CSRF_COOKIE = "styrai_login_csrf"
    LOGIN_CSRF_MAX_AGE = 10 * 60
    MAX_ACTIVE_SESSIONS = 4096

    SECURITY_HEADERS = {
        "Cache-Control": "no-store",
        "Content-Security-Policy": (
            "default-src 'self'; base-uri 'none'; object-src 'none'; "
            "frame-ancestors 'none'; form-action 'self'; script-src 'self'; "
            "style-src 'self'; img-src 'self' data:; connect-src 'self'"
        ),
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Permissions-Policy": (
            "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
        ),
        "Referrer-Policy": "no-referrer",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }

    def log_message(self, format: str, *args: object) -> None:
        return

    def end_headers(self) -> None:
        for name, value in self.SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def _send_json(
        self,
        payload: Any,
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(
        self,
        content: str,
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: Sequence[tuple[str, str]] = (),
    ) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        for name, value in extra_headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(encoded)

    def _redirect(
        self,
        location: str,
        *,
        status: HTTPStatus = HTTPStatus.SEE_OTHER,
        extra_headers: Sequence[tuple[str, str]] = (),
    ) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        for name, value in extra_headers:
            self.send_header(name, value)
        self.end_headers()

    def _cookie_value(self, name: str) -> str:
        raw_cookie = getattr(self, "headers", {}).get("Cookie", "")
        if not raw_cookie or len(raw_cookie) > 8192:
            return ""
        cookies = SimpleCookie()
        try:
            cookies.load(raw_cookie)
        except CookieError:
            return ""
        morsel = cookies.get(name)
        return morsel.value if morsel is not None else ""

    @classmethod
    def _session_cookie(cls, token: str) -> str:
        return (
            f"{cls.SESSION_COOKIE}={token}; Path=/; Max-Age={SESSION_TTL_SECONDS}; "
            "Secure; HttpOnly; SameSite=Strict"
        )

    @classmethod
    def _clear_cookie(cls, name: str, path: str = "/") -> str:
        return (
            f"{name}=; Path={path}; Max-Age=0; "
            "Expires=Thu, 01 Jan 1970 00:00:00 GMT; Secure; HttpOnly; SameSite=Strict"
        )

    @staticmethod
    def _safe_next_path(candidate: str | None) -> str:
        if not candidate or len(candidate) > 2048:
            return "/"
        parsed = urlparse(candidate)
        if (
            parsed.scheme
            or parsed.netloc
            or not candidate.startswith("/")
            or candidate.startswith("//")
            or "\\" in candidate
            or any(character in candidate for character in "\r\n")
        ):
            return "/"
        return candidate

    def _login_url(self) -> str:
        next_path = self._safe_next_path(getattr(self, "path", "/"))
        return f"/login?{urlencode({'next': next_path})}"

    @staticmethod
    def _session_fingerprint(token: str) -> str:
        return hashlib.sha256(token.encode("ascii", errors="ignore")).hexdigest()

    def _register_session(self, token: str) -> None:
        now = int(time.time())
        fingerprint = self._session_fingerprint(token)
        with self.active_sessions_lock:
            expired = [
                key for key, expiry in self.active_sessions.items() if expiry <= now
            ]
            for key in expired:
                self.active_sessions.pop(key, None)
            while len(self.active_sessions) >= self.MAX_ACTIVE_SESSIONS:
                oldest = min(self.active_sessions, key=self.active_sessions.get)
                self.active_sessions.pop(oldest, None)
            self.active_sessions[fingerprint] = now + SESSION_TTL_SECONDS

    def _session_is_active(self, token: str) -> bool:
        if not token:
            return False
        now = int(time.time())
        fingerprint = self._session_fingerprint(token)
        with self.active_sessions_lock:
            expiry = self.active_sessions.get(fingerprint)
            if expiry is None:
                return False
            if expiry <= now:
                self.active_sessions.pop(fingerprint, None)
                return False
            return True

    def _revoke_session(self, token: str) -> None:
        if not token:
            return
        with self.active_sessions_lock:
            self.active_sessions.pop(self._session_fingerprint(token), None)

    def _authenticate(self) -> bool:
        self.authenticated_username = None
        if not self.auth_users:
            return True
        if self.session_secret is None:
            return False
        token = self._cookie_value(self.SESSION_COOKIE)
        username = verify_session_token(
            token,
            self.session_secret,
            self.auth_users,
        )
        if username is not None and self._session_is_active(token):
            self.authenticated_username = username
            return True
        return False

    def _reject_unauthenticated(self, path: str) -> None:
        if path.startswith("/api/"):
            self._send_json(
                {
                    "error": "Authentication is required.",
                    "login_url": self._login_url(),
                },
                HTTPStatus.UNAUTHORIZED,
            )
            return
        self._redirect(self._login_url(), status=HTTPStatus.FOUND)

    def _read_form(self) -> dict[str, str]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid form length.") from exc
        if length <= 0 or length > 16_384:
            raise ValueError("Invalid form submission.")
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("application/x-www-form-urlencoded"):
            raise ValueError("Expected a browser form submission.")
        raw = self.rfile.read(length)
        try:
            fields = parse_qs(
                raw.decode("utf-8"),
                keep_blank_values=True,
                max_num_fields=8,
                strict_parsing=True,
            )
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("Invalid form submission.") from exc
        return {name: values[-1] for name, values in fields.items() if values}

    def _render_login(
        self,
        *,
        next_path: str = "/",
        username: str = "",
        error: str = "",
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        csrf_token = secrets.token_urlsafe(32)
        safe_next = self._safe_next_path(next_path)
        error_markup = (
            f'<p class="login-error" role="alert">{html.escape(error)}</p>'
            if error
            else ""
        )
        content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content="Sign in to the StyrAI governance demonstration" />
    <title>Sign in · StyrAI</title>
    <link rel="stylesheet" href="/login.css" />
  </head>
  <body>
    <main class="login-shell">
      <section class="login-card" aria-labelledby="login-title">
        <header class="login-brand">
          <span class="login-mark" aria-hidden="true">S</span>
          <span><strong>StyrAI</strong><small>AI governance operations</small></span>
        </header>
        <div class="login-copy">
          <p class="eyebrow">SECURE STAGING DEMONSTRATION</p>
          <h1 id="login-title">Sign in to the control plane</h1>
          <p>Use the access details provided by the StyrAI team. This environment accepts synthetic demonstration data only.</p>
        </div>
        {error_markup}
        <form method="post" action="/login" class="login-form">
          <input type="hidden" name="csrf_token" value="{html.escape(csrf_token, quote=True)}" />
          <input type="hidden" name="next" value="{html.escape(safe_next, quote=True)}" />
          <label for="username">Username</label>
          <input id="username" name="username" type="text" value="{html.escape(username, quote=True)}" autocomplete="username" autocapitalize="none" spellcheck="false" required autofocus />
          <label for="password">Password</label>
          <input id="password" name="password" type="password" autocomplete="current-password" required />
          <button type="submit">Sign in securely</button>
        </form>
        <footer><span aria-hidden="true">✓</span> Encrypted connection · Signed session · No production data</footer>
      </section>
    </main>
  </body>
</html>
"""
        csrf_cookie = (
            f"{self.LOGIN_CSRF_COOKIE}={csrf_token}; Path=/login; "
            f"Max-Age={self.LOGIN_CSRF_MAX_AGE}; Secure; HttpOnly; SameSite=Strict"
        )
        self._send_html(
            content,
            status,
            (("Set-Cookie", csrf_cookie),),
        )

    def _handle_login(self) -> None:
        if not self.auth_users:
            self._redirect("/")
            return
        try:
            fields = self._read_form()
        except ValueError as exc:
            self._render_login(error=str(exc), status=HTTPStatus.BAD_REQUEST)
            return
        next_path = self._safe_next_path(fields.get("next"))
        submitted_csrf = fields.get("csrf_token", "")
        cookie_csrf = self._cookie_value(self.LOGIN_CSRF_COOKIE)
        if (
            not submitted_csrf
            or not cookie_csrf
            or not secrets.compare_digest(submitted_csrf, cookie_csrf)
        ):
            self._render_login(
                next_path=next_path,
                username=fields.get("username", ""),
                error="The sign-in form expired. Please try again.",
                status=HTTPStatus.FORBIDDEN,
            )
            return
        username = fields.get("username", "")
        password = fields.get("password", "")
        stored_hash = self.auth_users.get(username)
        comparison_hash = stored_hash or next(iter(self.auth_users.values()))
        authenticated = verify_password(password, comparison_hash)
        if stored_hash is None or not authenticated:
            self._render_login(
                next_path=next_path,
                username=username,
                error="The username or password was not recognised.",
                status=HTTPStatus.UNAUTHORIZED,
            )
            return
        if self.session_secret is None:
            self._send_json(
                {"error": "Authentication is not configured."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        token = create_session_token(username, self.session_secret)
        self._register_session(token)
        self._redirect(
            next_path,
            extra_headers=(
                ("Set-Cookie", self._session_cookie(token)),
                (
                    "Set-Cookie",
                    self._clear_cookie(self.LOGIN_CSRF_COOKIE, path="/login"),
                ),
            ),
        )

    def _handle_logout(self) -> None:
        self._revoke_session(self._cookie_value(self.SESSION_COOKIE))
        self.authenticated_username = None
        self._redirect(
            "/login",
            extra_headers=(("Set-Cookie", self._clear_cookie(self.SESSION_COOKIE)),),
        )

    def _require_styrai_request_header(self) -> bool:
        if not self.auth_users:
            return True
        if getattr(self, "headers", {}).get("X-StyrAI-Request") == "1":
            return True
        self._send_json(
            {"error": "Authenticated changes require the StyrAI request header."},
            HTTPStatus.FORBIDDEN,
        )
        return False

    def _bind_authenticated_identity(
        self, path: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        username = self.authenticated_username
        if username is None:
            return payload
        bound = dict(payload)
        if path in {
            "/api/governance/inspect",
            "/api/simulate/call",
        }:
            bound["actor"] = username
        if path == "/api/pipeline-runs":
            bound.pop("actor", None)
            bound["operated_by"] = username
        if path.startswith("/api/actions/") and path.endswith("/approval"):
            bound["approver_id"] = username
        if path.startswith("/api/executions/") and path.endswith("/decision"):
            bound["approver_id"] = username
        if path.startswith("/api/pipeline-runs/") and path.endswith("/decision"):
            bound["demonstration_approver_id"] = bound.get(
                "demo_approver_id", bound.get("approver_id")
            )
            bound["approver_id"] = username
        if path.startswith("/api/governance/policies/") and path.endswith(
            "/activate"
        ):
            bound["approved_by"] = username
        return bound

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
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/login.css":
            self._send_static("login.css", "text/css; charset=utf-8")
            return
        if path == "/login":
            if self._authenticate():
                query = parse_qs(urlparse(self.path).query)
                self._redirect(
                    self._safe_next_path(query.get("next", ["/"])[-1]),
                    status=HTTPStatus.FOUND,
                )
                return
            query = parse_qs(urlparse(self.path).query)
            self._render_login(next_path=query.get("next", ["/"])[-1])
            return
        if path != "/api/health" and not self._authenticate():
            self._reject_unauthenticated(path)
            return
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
                if path.startswith("/api/"):
                    self._send_json(
                        {"error": "Route not found."}, HTTPStatus.NOT_FOUND
                    )
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
        except (GovernanceWorkflowError, ValueError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/login":
            self._handle_login()
            return
        if path == "/logout":
            self._handle_logout()
            return
        if not self._authenticate():
            self._reject_unauthenticated(path)
            return
        if not self._require_styrai_request_header():
            return
        try:
            payload = self._bind_authenticated_identity(path, self._read_json())
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
                if path.startswith("/api/"):
                    self._send_json(
                        {"error": "Route not found."}, HTTPStatus.NOT_FOUND
                    )
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
    auth_users = load_auth_users()
    session_secret = load_session_secret(required=bool(auth_users))
    application = DemoApplication(audit_path)
    handler = type(
        "ConfiguredStyrAIHandler",
        (StyrAIRequestHandler,),
        {
            "application": application,
            "auth_users": auth_users,
            "session_secret": session_secret,
            "active_sessions": {},
            "active_sessions_lock": threading.Lock(),
        },
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
