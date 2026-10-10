from __future__ import annotations

import unittest

from murphyos.web import (
    STYRAI_BUILD,
    STYRAI_CAPABILITIES,
    StyrAIRequestHandler,
)


class HealthCapabilityTests(unittest.TestCase):
    def test_health_identifies_upload_governance_build_and_capabilities(self) -> None:
        class CapturingHandler(StyrAIRequestHandler):
            def __init__(self) -> None:
                self.path = "/api/health"
                self.sent: object | None = None

            def _send_json(self, body: object, status: object = 200) -> None:
                self.sent = body

        handler = CapturingHandler()
        handler.do_GET()

        self.assertEqual(
            handler.sent,
            {
                "status": "ok",
                "product": "StyrAI",
                "mode": "synthetic-demo",
                "build": STYRAI_BUILD,
                "capabilities": list(STYRAI_CAPABILITIES),
            },
        )
        self.assertEqual(STYRAI_BUILD, "upload-governance-v1")
        self.assertIn("dataset-governance-run-v1", STYRAI_CAPABILITIES)


if __name__ == "__main__":
    unittest.main()
