from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from tradeharness.control.state import ControlState, StrategyControlState, RiskControlState
from tradeharness.ui_server import TradeHarnessAPIHandler

class DummyHandler(TradeHarnessAPIHandler):
    """A dummy sub-class that overrides HTTPServer binding methods so we can unit test it."""
    def __init__(self, *args, **kwargs):
        # Do not call super().__init__ as it blocks waiting for client request
        pass

    def send_response(self, code, message=None):
        self.response_code = code

    def send_header(self, keyword, value):
        if not hasattr(self, "headers_sent") or not isinstance(self.headers_sent, dict):
            self.headers_sent = {}
        self.headers_sent[keyword] = value

    def end_headers(self):
        with patch("http.server.BaseHTTPRequestHandler.end_headers"):
            TradeHarnessAPIHandler.end_headers(self)

    def send_error(self, code, message=None, explain=None):
        self.error_code = code
        self.error_message = message


class TradeHarnessUIServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        
        # Paths to mock
        self.log_path = self.temp_path / "episodes.jsonl"
        self.control_path = self.temp_path / "state.json"
        self.evolution_dir = self.temp_path / "evolution"
        self.evolution_dir.mkdir()

        # Instantiate Dummy Handler
        self.handler = DummyHandler()
        self.handler.wfile = io.BytesIO()
        self.handler.headers_sent = {}
        self.handler.response_code = None
        self.handler.ended_headers = False

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch("tradeharness.ui_server.DEFAULT_LOG_PATH")
    def test_get_episodes_empty_log(self, mock_log_path) -> None:
        mock_log_path.exists.return_value = False
        
        self.handler.get_episodes("")
        
        # Read response
        self.handler.wfile.seek(0)
        response = json.loads(self.handler.wfile.read().decode("utf-8"))
        self.assertEqual(response["episodes"], [])
        self.assertEqual(response["total"], 0)

    @patch("tradeharness.ui_server.DEFAULT_LOG_PATH")
    def test_get_episodes_populated_log(self, mock_log_path) -> None:
        mock_log_path.exists.return_value = True
        
        # Write dummy episodes
        episodes_data = [
            {"episode_id": "ep1", "task_id": "task1", "final_status": "SUCCESS", "steps": [{}, {}]},
            {"episode_id": "ep2", "task_id": "task2", "final_status": "FAILED", "steps": [{}, {}, {}]},
        ]
        
        # We mock open for the path
        content = "\n".join(json.dumps(ep) for ep in episodes_data) + "\n"
        with patch("builtins.open", unittest.mock.mock_open(read_data=content)):
            self.handler.get_episodes("limit=1")
            
            self.handler.wfile.seek(0)
            response = json.loads(self.handler.wfile.read().decode("utf-8"))
            
            # Since get_episodes reverses the list, the first item should be ep2
            self.assertEqual(response["total"], 2)
            self.assertEqual(len(response["episodes"]), 1)
            self.assertEqual(response["episodes"][0]["episode_id"], "ep2")
            self.assertEqual(response["episodes"][0]["step_count"], 3)
            # Full steps should be stripped in summary list
            self.assertNotIn("steps", response["episodes"][0])

    @patch("tradeharness.ui_server.DEFAULT_LOG_PATH")
    def test_get_episode_detail_not_found(self, mock_log_path) -> None:
        mock_log_path.exists.return_value = False
        
        self.handler.get_episode_detail("missing-id")
        self.assertEqual(self.handler.error_code, 404)

    @patch("tradeharness.ui_server.DEFAULT_LOG_PATH")
    def test_get_episode_detail_found(self, mock_log_path) -> None:
        mock_log_path.exists.return_value = True
        
        episode = {"episode_id": "ep1", "task_id": "task1", "steps": [{"observation": 1}]}
        content = json.dumps(episode) + "\n"
        
        with patch("builtins.open", unittest.mock.mock_open(read_data=content)):
            self.handler.get_episode_detail("ep1")
            
            self.handler.wfile.seek(0)
            response = json.loads(self.handler.wfile.read().decode("utf-8"))
            self.assertEqual(response["episode_id"], "ep1")
            self.assertEqual(len(response["steps"]), 1)

    @patch("tradeharness.ui_server.DEFAULT_CONTROL_STATE_PATH")
    def test_get_control_state(self, mock_control_path) -> None:
        dummy_state = ControlState(
            live_enabled=True,
            strategy=StrategyControlState(mode="dry_run", entry_quantity_btc=0.05),
            risk=RiskControlState(max_daily_loss_usdt=100.0)
        )
        with patch("tradeharness.ui_server.load_control_state", return_value=dummy_state):
            self.handler.get_control_state()
            
            self.handler.wfile.seek(0)
            response = json.loads(self.handler.wfile.read().decode("utf-8"))
            self.assertTrue(response["live_enabled"])
            self.assertEqual(response["strategy"]["mode"], "dry_run")
            self.assertEqual(response["risk"]["max_daily_loss_usdt"], 100.0)

    @patch("tradeharness.ui_server.DEFAULT_CONTROL_STATE_PATH")
    def test_post_control_state_updates_saved_state(self, mock_control_path) -> None:
        current_state = ControlState(
            live_enabled=False,
            strategy=StrategyControlState(mode="dry_run", entry_quantity_btc=0.01),
            risk=RiskControlState(max_daily_loss_usdt=50.0)
        )
        
        # Stub the payload read from request body
        post_payload = {
            "live_enabled": True,
            "strategy": {"mode": "live_trade", "entry_quantity_btc": 0.02},
            "risk": {"max_daily_loss_usdt": 10.0}
        }
        post_data = json.dumps(post_payload).encode("utf-8")
        self.handler.headers = {"Content-Length": str(len(post_data))}
        self.handler.rfile = io.BytesIO(post_data)
        
        with (
            patch("tradeharness.ui_server.load_control_state", return_value=current_state),
            patch("tradeharness.ui_server.save_control_state") as mock_save
        ):
            self.handler.post_control_state()
            
            self.handler.wfile.seek(0)
            response = json.loads(self.handler.wfile.read().decode("utf-8"))
            self.assertEqual(response["status"], "success")
            
            # Verify save was called with the updated properties
            mock_save.assert_called_once()
            saved_state = mock_save.call_args[0][1]
            self.assertTrue(saved_state.live_enabled)
            self.assertEqual(saved_state.strategy.mode, "live_trade")
            self.assertEqual(saved_state.strategy.entry_quantity_btc, 0.02)
            self.assertEqual(saved_state.risk.max_daily_loss_usdt, 10.0)

    @patch("tradeharness.ui_server.EVOLUTION_DIR")
    def test_get_evolution_status(self, mock_evo_dir) -> None:
        mock_evo_dir_path = self.temp_path / "evolution"
        mock_evo_dir.__truediv__.side_effect = lambda name: mock_evo_dir_path / name
        
        daily_report = mock_evo_dir_path / "daily-report.md"
        daily_report.write_text("Markdown evolution details", encoding="utf-8")
        
        pass_metrics = mock_evo_dir_path / "pass-metrics.json"
        pass_metrics.write_text('{"pass_ratio": 0.85}', encoding="utf-8")
        
        self.handler.get_evolution_status()
        
        self.handler.wfile.seek(0)
        response = json.loads(self.handler.wfile.read().decode("utf-8"))
        
        self.assertEqual(response["daily_report"], "Markdown evolution details")
        self.assertEqual(response["pass_metrics"]["pass_ratio"], 0.85)

    def test_cors_headers_are_injected(self) -> None:
        self.handler.end_headers()
        self.assertIn("Access-Control-Allow-Origin", self.handler.headers_sent)
        self.assertEqual(self.handler.headers_sent["Access-Control-Allow-Origin"], "*")


if __name__ == "__main__":
    unittest.main()
