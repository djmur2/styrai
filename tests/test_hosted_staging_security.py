from __future__ import annotations

import json
import re
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from murphyos.auth import (
    AuthenticationConfigurationError,
    MINIMUM_ITERATIONS,
    SESSION_TTL_SECONDS,
    create_session_token,
    generate_password_hash,
    load_auth_users,
    load_session_secret,
    verify_password,
    verify_session_token,
)
from murphyos.audit import HashChainedAuditLog
from murphyos.web import DemoApplication, StyrAIRequestHandler


class PasswordHashTests(unittest.TestCase):
    def test_hash_is_salted_encoded_and_verifiable_without_plaintext(self) -> None:
        password = "correct horse battery staple"
        encoded = generate_password_hash(
            password,
            iterations=MINIMUM_ITERATIONS,
            salt=b"0123456789abcdef",
        )

        self.assertTrue(encoded.startswith(f"pbkdf2_sha256${MINIMUM_ITERATIONS}$"))
        self.assertNotIn(password, encoded)
        self.assertTrue(verify_password(password, encoded))
        self.assertFalse(verify_password("incorrect", encoded))

    def test_auth_is_optional_but_configured_values_fail_closed(self) -> None:
        self.assertEqual(load_auth_users(environ={}), {})
        with self.assertRaises(AuthenticationConfigurationError):
            load_auth_users("{}")
        with self.assertRaises(AuthenticationConfigurationError):
            load_auth_users('{"founder": "plaintext-password"}')
        with self.assertRaises(AuthenticationConfigurationError):
            load_auth_users("not-json")

    def test_session_secret_is_separate_and_required_for_hosted_auth(self) -> None:
        self.assertIsNone(load_session_secret(environ={}))
        with self.assertRaises(AuthenticationConfigurationError):
            load_session_secret(environ={}, required=True)
        with self.assertRaises(AuthenticationConfigurationError):
            load_session_secret("too-short", required=True)
        with self.assertRaises(AuthenticationConfigurationError):
            load_session_secret("x" * 32 + "\n", required=True)
        self.assertEqual(load_session_secret("x" * 32), b"x" * 32)

    def test_session_tokens_are_signed_bounded_and_expire(self) -> None:
        now = 1_800_000_000
        secret = b"test-session-secret-with-at-least-32-bytes"
        users = {"founder": "unused-by-session-verification"}
        with self.assertRaises(ValueError):
            create_session_token("founder", b"too-short", now=now)
        token = create_session_token("founder", secret, now=now)
        second_token = create_session_token("founder", secret, now=now)

        self.assertNotEqual(token, second_token)
        self.assertEqual(
            verify_session_token(token, secret, users, now=now + 60), "founder"
        )
        self.assertEqual(
            verify_session_token(second_token, secret, users, now=now + 60),
            "founder",
        )
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        self.assertIsNone(verify_session_token(tampered, secret, users, now=now))
        self.assertIsNone(
            verify_session_token(
                token, secret, users, now=now + SESSION_TTL_SECONDS
            )
        )
        self.assertIsNone(
            verify_session_token(token, secret, {"other": "hash"}, now=now)
        )


class AuditLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.audit_path = Path(self.temporary_directory.name) / "staging-audit.jsonl"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_restart_continues_existing_audit_chain(self) -> None:
        first = DemoApplication(self.audit_path)
        prompt = "Unique benign restart evidence 928471."
        response = first.inspect_ai_prompt(
            {
                "model_id": "corporate-copilot-external",
                "actor": "founder-one",
                "classification": "internal",
                "use_case": "knowledge_and_drafting",
                "prompt": prompt,
            }
        )
        event_id = response["event"]["event_id"]
        before_restart = first.service.audit_log.records()

        second = DemoApplication(self.audit_path)
        after_restart = second.service.audit_log.records()

        self.assertGreater(len(after_restart), len(before_restart))
        self.assertTrue(any(record["action_id"] == event_id for record in after_restart))
        self.assertTrue(second.service.audit_log.verify())

    def test_explicit_reset_rotates_non_empty_audit_before_fresh_chain(self) -> None:
        application = DemoApplication(self.audit_path)
        application.inspect_ai_prompt(
            {
                "model_id": "corporate-copilot-external",
                "actor": "founder-one",
                "classification": "internal",
                "use_case": "knowledge_and_drafting",
                "prompt": "Unique reset evidence 184625.",
            }
        )
        old_contents = self.audit_path.read_text(encoding="utf-8")

        application.reset()

        archives = list(self.audit_path.parent.glob("staging-audit.reset-*.jsonl"))
        self.assertEqual(len(archives), 1)
        self.assertEqual(archives[0].read_text(encoding="utf-8"), old_contents)
        self.assertNotIn("governance.prompt_inspected", self.audit_path.read_text())
        current_records = application.service.audit_log.records()
        self.assertEqual(current_records[0]["index"], 0)
        self.assertEqual(
            current_records[0]["previous_hash"], HashChainedAuditLog.GENESIS_HASH
        )
        self.assertTrue(application.service.audit_log.verify())

    def test_empty_audit_rotation_is_a_no_op(self) -> None:
        self.audit_path.touch()
        log = HashChainedAuditLog(self.audit_path)
        self.assertIsNone(log.rotate())
        self.assertTrue(self.audit_path.exists())
        self.assertEqual(list(self.audit_path.parent.glob("*.reset-*.jsonl")), [])

    def test_prompt_audit_is_metadata_only_while_response_keeps_safe_preview(self) -> None:
        application = DemoApplication(self.audit_path)
        prompt = "Unique harmless board summary 715293."
        result = application.inspect_ai_prompt(
            {
                "model_id": "corporate-copilot-external",
                "actor": "founder-one",
                "classification": "internal",
                "use_case": "knowledge_and_drafting",
                "prompt": prompt,
            }
        )
        self.assertEqual(result["event"]["safe_preview"], prompt)

        record = next(
            item
            for item in application.service.audit_log.records()
            if item["event_type"] == "governance.prompt_inspected"
            and item["action_id"] == result["event"]["event_id"]
        )
        self.assertNotIn("safe_preview", record["payload"])
        self.assertNotIn(prompt, json.dumps(record))
        self.assertEqual(record["payload"]["prompt_hash"], result["event"]["prompt_hash"])
        self.assertFalse(record["payload"]["raw_input_stored"])
        self.assertTrue(application.service.audit_log.verify())


class HostedPipelineIdentityTests(unittest.TestCase):
    def test_handler_binds_supported_identity_fields_to_authenticated_user(self) -> None:
        handler = object.__new__(StyrAIRequestHandler)
        handler.authenticated_username = "founder-one"

        inspection = handler._bind_authenticated_identity(
            "/api/governance/inspect", {"actor": "spoofed-user"}
        )
        execution = handler._bind_authenticated_identity(
            "/api/executions/EXEC-1/decision", {"approver_id": "spoofed-user"}
        )
        activation = handler._bind_authenticated_identity(
            "/api/governance/policies/POL-1/activate",
            {"approved_by": "spoofed-user"},
        )
        pipeline = handler._bind_authenticated_identity(
            "/api/pipeline-runs/PIPE-1/decision",
            {"demo_approver_id": "payments-manager-demo"},
        )

        self.assertEqual(inspection["actor"], "founder-one")
        self.assertEqual(execution["approver_id"], "founder-one")
        self.assertEqual(activation["approved_by"], "founder-one")
        self.assertEqual(pipeline["approver_id"], "founder-one")
        self.assertEqual(
            pipeline["demonstration_approver_id"], "payments-manager-demo"
        )

    def test_authenticated_principals_are_separate_from_demo_roles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            application = DemoApplication(Path(directory) / "pipeline-audit.jsonl")
            run = application.start_pipeline(
                {
                    "pipeline_id": "finance-material-payment",
                    "case_id": "FIN-PAY-8842",
                    "actor": "spoofed-actor",
                    "operated_by": "founder-one",
                    "run_to_review": True,
                }
            )
            self.assertEqual(run["actor"], "payments-operator-demo")
            self.assertEqual(run["operated_by"], "founder-one")

            first = application.decide_pipeline(
                run["run_id"],
                {
                    "approver_id": "founder-one",
                    "demonstration_approver_id": "payments-manager-demo",
                    "approved": True,
                    "rationale": "First authenticated review completed.",
                },
            )
            self.assertEqual(first["governed_action"]["approved_by"], ["founder-one"])
            with self.assertRaises(ValueError):
                application.decide_pipeline(
                    run["run_id"],
                    {
                        "approver_id": "founder-two",
                        "demonstration_approver_id": "payments-manager-demo",
                        "approved": True,
                        "rationale": "Attempted reuse of a demo role.",
                    },
                )
            second = application.decide_pipeline(
                run["run_id"],
                {
                    "approver_id": "founder-two",
                    "demonstration_approver_id": "treasury-controller-demo",
                    "approved": True,
                    "rationale": "Independent authenticated review completed.",
                },
            )
            self.assertEqual(second["status"], "authorized")
            self.assertEqual(
                second["governed_action"]["approved_by"],
                ["founder-one", "founder-two"],
            )
            self.assertEqual(
                [item["demonstration_approver_id"] for item in second["approval_contexts"]],
                ["payments-manager-demo", "treasury-controller-demo"],
            )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class HostedHTTPTests(unittest.TestCase):
    PASSWORD = "hosted-test-password"
    SESSION_SECRET = b"hosted-test-session-secret-is-long-enough"

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.application = DemoApplication(
            Path(self.temporary_directory.name) / "hosted-http-audit.jsonl"
        )
        password_hash = generate_password_hash(
            self.PASSWORD,
            iterations=MINIMUM_ITERATIONS,
            salt=b"hosted-test-salt",
        )
        application = self.application

        class AuthenticatedHandler(StyrAIRequestHandler):
            auth_users = {"founder-one": password_hash}
            session_secret = HostedHTTPTests.SESSION_SECRET
            active_sessions: dict[str, int] = {}
            active_sessions_lock = threading.Lock()

        AuthenticatedHandler.application = application
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AuthenticatedHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.opener = build_opener(_NoRedirect)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary_directory.cleanup()

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        cookie: str = "",
        styrai_header: bool = False,
        payload: dict[str, object] | None = None,
        form: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, object, object]:
        headers = dict(extra_headers or {})
        if cookie:
            headers["Cookie"] = cookie
        if styrai_header:
            headers["X-StyrAI-Request"] = "1"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if form is not None:
            data = urlencode(form).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        request = Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            response = self.opener.open(request, timeout=3)  # noqa: S310
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            parsed: object = body.decode("utf-8")
            if "application/json" in content_type:
                parsed = json.loads(body)
            return response.status, response.headers, parsed

    def login(
        self,
        *,
        password: str | None = None,
        next_path: str = "/",
    ) -> tuple[int, object, object, str]:
        status, headers, body = self.request(
            f"/login?{urlencode({'next': next_path})}"
        )
        self.assertEqual(status, 200)
        csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', str(body))
        self.assertIsNotNone(csrf_match)
        csrf_token = csrf_match.group(1)
        csrf_cookie = headers.get("Set-Cookie").split(";", 1)[0]
        status, headers, body = self.request(
            "/login",
            method="POST",
            cookie=csrf_cookie,
            form={
                "csrf_token": csrf_token,
                "next": next_path,
                "username": "founder-one",
                "password": password or self.PASSWORD,
            },
        )
        session_cookie = ""
        for value in headers.get_all("Set-Cookie", []):
            if value.startswith("__Host-styrai_session="):
                session_cookie = value.split(";", 1)[0]
        return status, headers, body, session_cookie

    def assert_security_headers(self, headers: object) -> None:
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")
        self.assertIn("frame-ancestors 'none'", headers.get("Content-Security-Policy"))
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_public_health_and_login_then_protected_browser_and_api_routes(self) -> None:
        health_status, health_headers, health = self.request("/api/health")
        self.assertEqual(health_status, 200)
        self.assertEqual(health["status"], "ok")
        self.assert_security_headers(health_headers)

        login_status, login_headers, login_body = self.request(
            "/login?next=%2F%3Fpresentation%3D1"
        )
        self.assertEqual(login_status, 200)
        self.assertIn("Sign in to the control plane", login_body)
        self.assertIn('autocomplete="current-password"', login_body)
        self.assertNotIn(self.PASSWORD, login_body)
        self.assertIn("Secure", login_headers.get("Set-Cookie"))
        self.assertIn("HttpOnly", login_headers.get("Set-Cookie"))
        self.assertIn("SameSite=Strict", login_headers.get("Set-Cookie"))
        css_status, _, css = self.request("/login.css")
        self.assertEqual(css_status, 200)
        self.assertIn(".login-card", css)

        page_status, page_headers, _ = self.request("/?presentation=1")
        self.assertEqual(page_status, 302)
        self.assertEqual(
            page_headers.get("Location"),
            "/login?next=%2F%3Fpresentation%3D1",
        )
        self.assertIsNone(page_headers.get("WWW-Authenticate"))
        api_status, _, error = self.request("/api/governance")
        self.assertEqual(api_status, 401)
        self.assertEqual(error["error"], "Authentication is required.")
        self.assertIn("/login?", error["login_url"])

        status, headers, _, cookie = self.login(next_path="/?presentation=1")
        self.assertEqual(status, 303)
        self.assertEqual(headers.get("Location"), "/?presentation=1")
        self.assertTrue(cookie.startswith("__Host-styrai_session="))
        session_header = next(
            value
            for value in headers.get_all("Set-Cookie")
            if value.startswith("__Host-styrai_session=")
        )
        self.assertIn("Secure", session_header)
        self.assertIn("HttpOnly", session_header)
        self.assertIn("SameSite=Strict", session_header)

        ok_status, ok_headers, body = self.request("/", cookie=cookie)
        self.assertEqual(ok_status, 200)
        self.assertIn("StyrAI", body)
        self.assert_security_headers(ok_headers)
        missing_status, missing_headers, _ = self.request(
            "/missing", cookie=cookie
        )
        self.assertEqual(missing_status, 404)
        self.assert_security_headers(missing_headers)
        api_missing_status, api_missing_headers, api_missing = self.request(
            "/api/not-a-real-route", cookie=cookie
        )
        self.assertEqual(api_missing_status, 404)
        self.assertEqual(api_missing["error"], "Route not found.")
        self.assertIn("application/json", api_missing_headers.get("Content-Type"))

    def test_simultaneous_login_forms_keep_independent_csrf_cookies(self) -> None:
        forms: list[tuple[str, str, str]] = []
        for tab_number in range(5):
            status, headers, body = self.request(
                f"/login?{urlencode({'next': f'/tab-{tab_number}'})}"
            )
            self.assertEqual(status, 200)
            token_match = re.search(
                r'name="csrf_token" value="([^"]+)"', str(body)
            )
            self.assertIsNotNone(token_match)
            csrf_token = token_match.group(1)
            csrf_cookie = headers.get("Set-Cookie").split(";", 1)[0]
            cookie_name = csrf_cookie.split("=", 1)[0]
            self.assertTrue(
                cookie_name.startswith(StyrAIRequestHandler.LOGIN_CSRF_COOKIE_PREFIX)
            )
            forms.append((csrf_token, csrf_cookie, cookie_name))

        self.assertEqual(len({cookie_name for _, _, cookie_name in forms}), 5)
        browser_cookies = "; ".join(cookie for _, cookie, _ in forms)

        for form_index in (0, 4):
            csrf_token, _, cookie_name = forms[form_index]
            status, headers, _ = self.request(
                "/login",
                method="POST",
                cookie=browser_cookies,
                form={
                    "csrf_token": csrf_token,
                    "next": f"/tab-{form_index}",
                    "username": "founder-one",
                    "password": self.PASSWORD,
                },
            )
            self.assertEqual(status, 303)
            self.assertEqual(headers.get("Location"), f"/tab-{form_index}")
            self.assertTrue(
                any(
                    value.startswith(f"{cookie_name}=") and "Max-Age=0" in value
                    for value in headers.get_all("Set-Cookie", [])
                )
            )

        invalid_status, _, invalid_body = self.request(
            "/login",
            method="POST",
            cookie=browser_cookies,
            form={
                "csrf_token": f"{forms[2][0]}-tampered",
                "next": "/",
                "username": "founder-one",
                "password": self.PASSWORD,
            },
        )
        self.assertEqual(invalid_status, 403)
        self.assertIn("form expired", invalid_body)

    def test_login_rejects_bad_credentials_csrf_and_open_redirects(self) -> None:
        status, headers, body, cookie = self.login(
            password="wrong-password",
            next_path="https://attacker.example/collect",
        )
        self.assertEqual(status, 401)
        self.assertFalse(cookie)
        self.assertIn("not recognised", body)
        self.assertNotIn("wrong-password", body)
        self.assertIsNone(headers.get("Location"))

        status, _, body = self.request(
            "/login",
            method="POST",
            form={
                "csrf_token": "missing-cookie-token",
                "next": "/",
                "username": "founder-one",
                "password": self.PASSWORD,
            },
        )
        self.assertEqual(status, 403)
        self.assertIn("form expired", body)

        _, login_headers, login_body = self.request("/login")
        csrf_token = re.search(
            r'name="csrf_token" value="([^"]+)"', str(login_body)
        ).group(1)
        csrf_cookie = login_headers.get("Set-Cookie").split(";", 1)[0]
        status, headers, _, cookie = self.login(next_path="//attacker.example")
        self.assertEqual(status, 303)
        self.assertEqual(headers.get("Location"), "/")
        self.assertTrue(cookie)

        status, headers, _ = self.request(
            "/login",
            method="POST",
            cookie=csrf_cookie,
            form={
                "csrf_token": csrf_token,
                "next": "https://attacker.example/collect",
                "username": "founder-one",
                "password": self.PASSWORD,
            },
        )
        self.assertEqual(status, 303)
        self.assertEqual(headers.get("Location"), "/")

    def test_tampered_and_expired_session_cookies_are_rejected(self) -> None:
        status, _, _, cookie = self.login()
        self.assertEqual(status, 303)
        tampered = cookie[:-1] + ("A" if cookie[-1] != "A" else "B")
        status, _, _ = self.request("/api/governance", cookie=tampered)
        self.assertEqual(status, 401)

        expired_token = create_session_token(
            "founder-one",
            self.SESSION_SECRET,
            now=int(time.time()) - SESSION_TTL_SECONDS - 1,
        )
        status, _, _ = self.request(
            "/api/governance",
            cookie=f"__Host-styrai_session={expired_token}",
        )
        self.assertEqual(status, 401)

        status, _, _ = self.request(
            "/",
            extra_headers={"Authorization": "Basic Zm91bmRlci1vbmU6aG9zdGVkLXRlc3QtcGFzc3dvcmQ="},
        )
        self.assertEqual(status, 302)

    def test_logout_clears_session_cookie(self) -> None:
        _, _, _, cookie = self.login()
        status, headers, _ = self.request(
            "/logout", method="POST", cookie=cookie
        )
        self.assertEqual(status, 303)
        self.assertEqual(headers.get("Location"), "/login")
        cleared = headers.get("Set-Cookie")
        self.assertIn("__Host-styrai_session=", cleared)
        self.assertIn("Max-Age=0", cleared)
        self.assertIn("HttpOnly", cleared)
        replay_status, _, _ = self.request("/api/governance", cookie=cookie)
        self.assertEqual(replay_status, 401)

    def test_direct_login_post_is_safe_when_authentication_is_disabled(self) -> None:
        application = self.application

        class NoAuthenticationHandler(StyrAIRequestHandler):
            auth_users = {}
            session_secret = None

        NoAuthenticationHandler.application = application
        server = ThreadingHTTPServer(("127.0.0.1", 0), NoAuthenticationHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_port}/login",
                data=b"",
                method="POST",
            )
            try:
                response = self.opener.open(request, timeout=3)  # noqa: S310
            except HTTPError as exc:
                response = exc
            with response:
                self.assertEqual(response.status, 303)
                self.assertEqual(response.headers.get("Location"), "/")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_authenticated_posts_require_marker_before_any_mutation(self) -> None:
        _, _, _, cookie = self.login()
        before = len(self.application.ai_governance_state()["runtime_events"])
        payload = {
            "model_id": "corporate-copilot-external",
            "actor": "spoofed-user",
            "classification": "internal",
            "use_case": "knowledge_and_drafting",
            "prompt": "Safe synthetic request.",
        }
        status, headers, error = self.request(
            "/api/governance/inspect",
            method="POST",
            cookie=cookie,
            payload=payload,
        )
        self.assertEqual(status, 403)
        self.assertIn("request header", error["error"])
        self.assertEqual(
            len(self.application.ai_governance_state()["runtime_events"]), before
        )
        self.assert_security_headers(headers)

    def test_authenticated_actor_and_approver_are_server_bound(self) -> None:
        _, _, _, cookie = self.login()
        prompt = "Unique authenticated prompt 397251."
        status, _, inspection = self.request(
            "/api/governance/inspect",
            method="POST",
            cookie=cookie,
            styrai_header=True,
            payload={
                "model_id": "corporate-copilot-external",
                "actor": "spoofed-user",
                "classification": "internal",
                "use_case": "knowledge_and_drafting",
                "prompt": prompt,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(inspection["event"]["actor"], "founder-one")

        waiting_action = next(
            item
            for item in self.application.state()["actions"]
            if item["status"] == "waiting_approval"
        )
        action_id = waiting_action["action"]["action_id"]
        status, _, approval = self.request(
            f"/api/actions/{action_id}/approval",
            method="POST",
            cookie=cookie,
            styrai_header=True,
            payload={
                "approver_id": "spoofed-approver",
                "approved": True,
                "rationale": "Reviewed the synthetic action.",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(approval["approved_by"], ["founder-one"])
        serialized_audit = json.dumps(self.application.service.audit_log.records())
        self.assertNotIn("spoofed-user", serialized_audit)
        self.assertNotIn("spoofed-approver", serialized_audit)
        self.assertNotIn(self.PASSWORD, serialized_audit)


if __name__ == "__main__":
    unittest.main()
