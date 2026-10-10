from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from murphyos.web import _browser_urls, _open_browser_when_ready, build_parser


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class DemoLaunchTests(unittest.TestCase):
    def test_open_browser_flag_is_explicit_and_defaults_off(self) -> None:
        parser = build_parser()
        self.assertFalse(parser.parse_args([]).open_browser)
        self.assertTrue(parser.parse_args(["--open-browser"]).open_browser)

    def test_presenter_url_uses_requested_host_and_port(self) -> None:
        health_url, presentation_url = _browser_urls("127.0.0.1", 9123)
        self.assertEqual(health_url, "http://127.0.0.1:9123/api/health")
        self.assertEqual(
            presentation_url,
            "http://127.0.0.1:9123/?presentation=1",
        )

    @patch("murphyos.web.webbrowser.open")
    @patch("murphyos.web.urlopen")
    def test_browser_opens_only_after_healthy_styrai_response(
        self, mock_urlopen, mock_open
    ) -> None:
        response = MagicMock()
        response.read.return_value = b'{"status":"ok","product":"StyrAI"}'
        mock_urlopen.return_value.__enter__.return_value = response

        _open_browser_when_ready(
            "http://127.0.0.1:8765/api/health",
            "http://127.0.0.1:8765/?presentation=1",
            timeout_seconds=0.1,
        )

        mock_urlopen.assert_called_once()
        mock_open.assert_called_once_with(
            "http://127.0.0.1:8765/?presentation=1"
        )

    def test_founder_launcher_probes_governance_and_passes_selected_port(self) -> None:
        launcher = (PROJECT_ROOT / "Start StyrAI Demo.command").read_text()

        self.assertIn(
            'python3 -m murphyos.web --port "$DEMO_PORT" --open-browser',
            launcher,
        )
        self.assertIn("/api/health", launcher)
        self.assertIn("/api/governance", launcher)
        self.assertIn("?presentation=1", launcher)
        self.assertIn("PORT_START=8765", launcher)
        self.assertIn("PORT_END=8775", launcher)
        self.assertIn('audit.get("valid") is True', launcher)
        self.assertIn(
            'enforcement.get("inspection_point") == "before_provider_boundary"',
            launcher,
        )
        self.assertNotIn("<title>StyrAI", launcher)
        self.assertNotIn("rm ", launcher)


if __name__ == "__main__":
    unittest.main()
