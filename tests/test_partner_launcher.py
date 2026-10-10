from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, call, patch

import launch_styrai


class PartnerLauncherTests(unittest.TestCase):
    @patch("launch_styrai._read_json")
    def test_current_server_requires_governance_boundary_and_valid_audit(
        self, read_json
    ) -> None:
        read_json.side_effect = [
            {"status": "ok", "product": "StyrAI"},
            {
                "mode": "synthetic_local_control_plane",
                "models": [{"model_id": "demo"}],
                "metrics": {"deployed_models": 1},
                "enforcement": {
                    "inspection_point": "before_provider_boundary"
                },
                "audit": {"valid": True},
            },
            {
                "schema": "styrai.synthetic-ai-outcomes.v1",
                "formats": ["csv", "json"],
            },
        ]

        self.assertTrue(launch_styrai._is_current_styrai(8765))
        self.assertEqual(
            read_json.call_args_list,
            [
                call(8765, "/api/health"),
                call(8765, "/api/governance"),
                call(8765, "/api/governance/dataset-schema"),
            ],
        )

    @patch("launch_styrai._read_json")
    def test_old_server_without_dataset_upload_capability_is_not_reused(
        self, read_json
    ) -> None:
        read_json.side_effect = [
            {"status": "ok", "product": "StyrAI"},
            {
                "mode": "synthetic_local_control_plane",
                "models": [{"model_id": "demo"}],
                "metrics": {"deployed_models": 1},
                "enforcement": {
                    "inspection_point": "before_provider_boundary"
                },
                "audit": {"valid": True},
            },
            ValueError("Unexpected token '<', '<!DOCTYPE' is not valid JSON"),
        ]

        self.assertFalse(launch_styrai._is_current_styrai(8765))
        self.assertEqual(
            read_json.call_args_list[-1],
            call(8765, "/api/governance/dataset-schema"),
        )

    @patch("launch_styrai._read_json")
    def test_server_with_stale_dataset_schema_is_not_reused(
        self, read_json
    ) -> None:
        read_json.side_effect = [
            {"status": "ok", "product": "StyrAI"},
            {
                "mode": "synthetic_local_control_plane",
                "models": [{"model_id": "demo"}],
                "metrics": {"deployed_models": 1},
                "enforcement": {
                    "inspection_point": "before_provider_boundary"
                },
                "audit": {"valid": True},
            },
            {
                "schema": "styrai.synthetic-ai-outcomes.v0",
                "formats": ["csv", "json"],
            },
        ]

        self.assertFalse(launch_styrai._is_current_styrai(8765))

    @patch("launch_styrai.webbrowser.open")
    @patch("launch_styrai._is_free", return_value=False)
    @patch("launch_styrai._is_current_styrai")
    def test_existing_verified_server_is_opened(
        self, is_current, _is_free, browser_open
    ) -> None:
        is_current.side_effect = lambda port: port == 8767

        self.assertEqual(launch_styrai.main(), 0)
        browser_open.assert_called_once_with(
            "http://127.0.0.1:8767/?presentation=1"
        )

    @patch("launch_styrai.subprocess.run")
    @patch("launch_styrai._is_free")
    @patch("launch_styrai._is_current_styrai", return_value=False)
    def test_first_free_port_starts_current_package(
        self, _is_current, is_free, run
    ) -> None:
        is_free.side_effect = lambda port: port == 8766
        run.return_value = MagicMock(returncode=0)

        self.assertEqual(launch_styrai.main(), 0)
        run.assert_called_once_with(
            [
                sys.executable,
                "-m",
                "murphyos.web",
                "--port",
                "8766",
                "--open-browser",
            ],
            cwd=launch_styrai.PROJECT_ROOT,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
