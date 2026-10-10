from __future__ import annotations

import base64
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from murphyos.auth import (
    AuthenticationConfigurationError,
    MINIMUM_ITERATIONS,
    generate_password_hash,
    load_auth_users,
    verify_password,
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


class HostedHTTPTests(unittest.TestCase):
    PASSWORD = "hosted-test-password"

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

        AuthenticatedHandler.application = application
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), AuthenticatedHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary_directory.cleanup()

    @staticmethod
    def _authorization(username: str, password: str) -> str:
        credentials = base64.b64encode(
            f"{username}:{password}".encode("utf-8")
        ).decode("ascii")
        return f"Basic {credentials}"

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        authenticated: bool = False,
        password: str | None = None,
        styrai_header: bool = False,
        payload: dict[str, object] | None = None,
    ) -> tuple[int, object, object]:
        headers: dict[str, str] = {}
        if authenticated:
            headers["Authorization"] = self._authorization(
                "founder-one", password or self.PASSWORD
            )
        if styrai_header:
            headers["X-StyrAI-Request"] = "1"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            response = urlopen(request, timeout=2)  # noqa: S310
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            parsed: object = body.decode("utf-8")
            if "application/json" in content_type:
                parsed = json.loads(body)
            return response.status, response.headers, parsed

    def assert_security_headers(self, headers: object) -> None:
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")
        self.assertIn("frame-ancestors 'none'", headers.get("Content-Security-Policy"))
        self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_health_is_public_and_every_other_get_requires_valid_auth(self) -> None:
        health_status, health_headers, health = self.request("/api/health")
        self.assertEqual(health_status, 200)
        self.assertEqual(health["status"], "ok")
        self.assert_security_headers(health_headers)

        unauthorized_status, unauthorized_headers, _ = self.request("/")
        self.assertEqual(unauthorized_status, 401)
        self.assertIn("Basic realm=", unauthorized_headers.get("WWW-Authenticate"))
        self.assert_security_headers(unauthorized_headers)

        wrong_status, _, _ = self.request(
            "/", authenticated=True, password="wrong-password"
        )
        self.assertEqual(wrong_status, 401)

        ok_status, ok_headers, body = self.request("/", authenticated=True)
        self.assertEqual(ok_status, 200)
        self.assertIn("StyrAI", body)
        self.assert_security_headers(ok_headers)

        missing_status, missing_headers, _ = self.request(
            "/missing", authenticated=True
        )
        self.assertEqual(missing_status, 404)
        self.assert_security_headers(missing_headers)

    def test_authenticated_posts_require_marker_before_any_mutation(self) -> None:
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
            authenticated=True,
            payload=payload,
        )
        self.assertEqual(status, 403)
        self.assertIn("request header", error["error"])
        self.assertEqual(
            len(self.application.ai_governance_state()["runtime_events"]), before
        )
        self.assert_security_headers(headers)

    def test_authenticated_actor_and_approver_are_server_bound(self) -> None:
        prompt = "Unique authenticated prompt 397251."
        status, _, inspection = self.request(
            "/api/governance/inspect",
            method="POST",
            authenticated=True,
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
            authenticated=True,
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
