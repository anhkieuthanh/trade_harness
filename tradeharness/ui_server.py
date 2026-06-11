from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tradeharness.control.state import (
    ControlState,
    StrategyControlState,
    RiskControlState,
    load_control_state,
    save_control_state,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_PATH = REPO_ROOT / "var" / "trajectories" / "episodes.jsonl"
DEFAULT_CONTROL_STATE_PATH = REPO_ROOT / "var" / "control" / "state.json"
EVOLUTION_DIR = REPO_ROOT / "var" / "evolution"

# Thread safety lock for updating control state and running evolution
_state_lock = threading.Lock()

# Global evolution status tracking
_evolution_status = {
    "status": "idle",
    "last_run": None,
    "error": None,
    "stdout": "",
    "stderr": ""
}

class TradeHarnessAPIHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS for local Vite Svelte development (port 5173 / any)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path_parts = [p for p in parsed_path.path.split("/") if p]

        # Route API endpoints
        if len(path_parts) >= 2 and path_parts[0] == "api":
            endpoint = path_parts[1]
            if endpoint == "episodes":
                if len(path_parts) == 3:
                    self.get_episode_detail(path_parts[2])
                else:
                    self.get_episodes(parsed_path.query)
                return
            elif endpoint == "control":
                self.get_control_state()
                return
            elif endpoint == "evolution":
                if len(path_parts) == 3 and path_parts[2] == "status":
                    self.get_evolution_status()
                    return

            self.send_error(404, "API Endpoint Not Found")
            return

        # Route Static Files / SPA Fallback
        self.serve_static_file(parsed_path.path)

    def do_POST(self):
        parsed_path = urlparse(self.path)
        path_parts = [p for p in parsed_path.path.split("/") if p]

        if len(path_parts) >= 2 and path_parts[0] == "api":
            endpoint = path_parts[1]
            if endpoint == "control":
                self.post_control_state()
                return
            elif endpoint == "evolution" and len(path_parts) == 3 and path_parts[2] == "run":
                self.run_evolution()
                return

            self.send_error(404, "API Endpoint Not Found")
            return

        self.send_error(400, "Bad Request")

    def get_episodes(self, query_string: str):
        query = parse_qs(query_string)
        limit = 100
        if "limit" in query:
            try:
                limit = int(query["limit"][0])
            except ValueError:
                pass

        if not DEFAULT_LOG_PATH.exists():
            self.send_json_response({"episodes": [], "total": 0})
            return

        try:
            episodes = []
            with open(DEFAULT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        ep = json.loads(line)
                        # Keep list payload light by excluding full steps details
                        steps = ep.get("steps", [])
                        episodes.append({
                            "episode_id": ep.get("episode_id"),
                            "task_id": ep.get("task_id"),
                            "harness_version": ep.get("harness_version"),
                            "symbol": ep.get("symbol"),
                            "mode": ep.get("mode"),
                            "started_at": ep.get("started_at"),
                            "ended_at": ep.get("ended_at"),
                            "final_status": ep.get("final_status"),
                            "termination_reason": ep.get("termination_reason"),
                            "step_count": len(steps),
                            "final_outcome": ep.get("final_outcome"),
                        })
                    except json.JSONDecodeError:
                        continue
            
            # Reverse to get newest first
            episodes.reverse()
            total = len(episodes)
            self.send_json_response({
                "episodes": episodes[:limit],
                "total": total
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def get_episode_detail(self, episode_id: str):
        if not DEFAULT_LOG_PATH.exists():
            self.send_error(404, "Episode not found")
            return

        try:
            found_ep = None
            with open(DEFAULT_LOG_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        ep = json.loads(line)
                        if ep.get("episode_id") == episode_id:
                            found_ep = ep
                            break
                    except json.JSONDecodeError:
                        continue

            if found_ep:
                self.send_json_response(found_ep)
            else:
                self.send_error(404, "Episode not found")
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def get_control_state(self):
        try:
            state = load_control_state(DEFAULT_CONTROL_STATE_PATH)
            # Serialize control state
            self.send_json_response({
                "live_enabled": state.live_enabled,
                "offline_evolution_enabled": state.offline_evolution_enabled,
                "offline_evolution_time": state.offline_evolution_time,
                "last_offline_evolution_run_date": state.last_offline_evolution_run_date,
                "strategy": {
                    "mode": state.strategy.mode,
                    "entry_quantity_btc": state.strategy.entry_quantity_btc,
                    "hold_seconds": state.strategy.hold_seconds,
                    "cooldown_seconds": state.strategy.cooldown_seconds,
                },
                "risk": {
                    "max_daily_loss_usdt": state.risk.max_daily_loss_usdt,
                    "max_open_positions": state.risk.max_open_positions,
                    "loss_cooldown_seconds": state.risk.loss_cooldown_seconds,
                    "hard_stop_candle_range_pct": state.risk.hard_stop_candle_range_pct,
                }
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def post_control_state(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))

            with _state_lock:
                # Load existing to preserve fields not sent
                current = load_control_state(DEFAULT_CONTROL_STATE_PATH)
                
                strategy_payload = payload.get("strategy", {})
                risk_payload = payload.get("risk", {})

                strategy_state = StrategyControlState(
                    mode=strategy_payload.get("mode", current.strategy.mode),
                    entry_quantity_btc=float(strategy_payload.get("entry_quantity_btc", current.strategy.entry_quantity_btc)),
                    hold_seconds=int(strategy_payload.get("hold_seconds", current.strategy.hold_seconds)),
                    cooldown_seconds=int(strategy_payload.get("cooldown_seconds", current.strategy.cooldown_seconds)),
                )

                risk_state = RiskControlState(
                    max_daily_loss_usdt=float(risk_payload.get("max_daily_loss_usdt", current.risk.max_daily_loss_usdt)),
                    max_open_positions=int(risk_payload.get("max_open_positions", current.risk.max_open_positions)),
                    loss_cooldown_seconds=int(risk_payload.get("loss_cooldown_seconds", current.risk.loss_cooldown_seconds)),
                    hard_stop_candle_range_pct=float(risk_payload.get("hard_stop_candle_range_pct", current.risk.hard_stop_candle_range_pct)),
                )

                updated = ControlState(
                    live_enabled=bool(payload.get("live_enabled", current.live_enabled)),
                    offline_evolution_enabled=bool(payload.get("offline_evolution_enabled", current.offline_evolution_enabled)),
                    offline_evolution_time=str(payload.get("offline_evolution_time", current.offline_evolution_time)),
                    last_offline_evolution_run_date=current.last_offline_evolution_run_date,
                    strategy=strategy_state,
                    risk=risk_state,
                )

                save_control_state(DEFAULT_CONTROL_STATE_PATH, updated)
            
            self.send_json_response({"status": "success"})
        except Exception as e:
            self.send_json_response({"error": str(e)}, status=500)

    def get_evolution_status(self):
        # Read from current local artifacts
        daily_report_path = EVOLUTION_DIR / "daily-report.md"
        pass_metrics_path = EVOLUTION_DIR / "pass-metrics.json"

        daily_report = ""
        if daily_report_path.exists():
            try:
                daily_report = daily_report_path.read_text(encoding="utf-8")
            except OSError:
                pass

        pass_metrics = {}
        if pass_metrics_path.exists():
            try:
                pass_metrics = json.loads(pass_metrics_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass

        self.send_json_response({
            "run_status": _evolution_status,
            "daily_report": daily_report,
            "pass_metrics": pass_metrics
        })

    def run_evolution(self):
        global _evolution_status
        if _evolution_status["status"] == "running":
            self.send_json_response({"status": "already_running"})
            return

        _evolution_status["status"] = "running"
        _evolution_status["error"] = None
        _evolution_status["stdout"] = ""
        _evolution_status["stderr"] = ""

        def worker():
            global _evolution_status
            try:
                process = subprocess.run(
                    ["python3", "-m", "tradeharness.evolution.main"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True
                )
                _evolution_status["stdout"] = process.stdout
                _evolution_status["stderr"] = process.stderr
                if process.returncode == 0:
                    _evolution_status["status"] = "success"
                else:
                    _evolution_status["status"] = "error"
                    _evolution_status["error"] = f"Exit code {process.returncode}"
            except Exception as e:
                _evolution_status["status"] = "error"
                _evolution_status["error"] = str(e)
            finally:
                from datetime import datetime, timezone
                _evolution_status["last_run"] = datetime.now(timezone.utc).isoformat()

        thread = threading.Thread(target=worker)
        thread.start()
        self.send_json_response({"status": "started"})

    def serve_static_file(self, req_path: str):
        # Default fallback to index.html for SPA client-side routing
        ui_dist = REPO_ROOT / "ui" / "dist"
        
        # Clean path to prevent directory traversal
        clean_path = req_path.lstrip("/")
        if not clean_path:
            clean_path = "index.html"
            
        file_path = ui_dist / clean_path
        
        # Security check
        if not str(file_path.resolve()).startswith(str(ui_dist.resolve())):
            file_path = ui_dist / "index.html"

        if not file_path.exists() or file_path.is_dir():
            file_path = ui_dist / "index.html"

        if not file_path.exists():
            self.send_error(404, "UI Static Files Not Found. Build UI first.")
            return

        content_type = "text/html"
        suffix = file_path.suffix.lower()
        if suffix == ".js":
            content_type = "application/javascript"
        elif suffix == ".css":
            content_type = "text/css"
        elif suffix == ".png":
            content_type = "image/png"
        elif suffix == ".svg":
            content_type = "image/svg+xml"
        elif suffix == ".ico":
            content_type = "image/x-icon"
        elif suffix == ".json":
            content_type = "application/json"

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except OSError:
            self.send_error(500, "Internal Server Error serving static file")

    def send_json_response(self, data: dict | list, status: int = 200):
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_error(500, f"JSON serialization error: {e}")

def run_server(port: int = 8080):
    server_address = ("", port)
    httpd = HTTPServer(server_address, TradeHarnessAPIHandler)
    print(f"Starting TradeHarness UI Server on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    import sys
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port)
