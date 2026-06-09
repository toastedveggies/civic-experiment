from __future__ import annotations

import json
import mimetypes
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from policy_tracker.dashboard import build_dashboard_summary


ASSET_DIR = Path(__file__).resolve().parent / "dashboard_static"


class DashboardRequestHandler(BaseHTTPRequestHandler):
    server_version = "PolicyTrackerDashboard/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/api/health", "/health"}:
            self.write_json({"status": "ok"})
            return
        if parsed.path == "/api/summary":
            self.write_json(
                build_dashboard_summary(
                    db_path=self.server.db_path,
                    config_dir=self.server.config_dir,
                    state_dir=self.server.state_dir,
                )
            )
            return
        self.serve_static(parsed.path)

    def log_message(self, format: str, *args: Any) -> None:
        if not self.server.quiet:
            super().log_message(format, *args)

    def serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            asset_path = ASSET_DIR / "index.html"
        else:
            requested = path.lstrip("/")
            asset_path = (ASSET_DIR / requested).resolve()
            if ASSET_DIR not in asset_path.parents and asset_path != ASSET_DIR:
                self.write_error(403, "Forbidden")
                return

        if not asset_path.exists() or not asset_path.is_file():
            self.write_error(404, "Not found")
            return

        content_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
        payload = asset_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def write_error(self, status: int, message: str) -> None:
        self.write_json({"error": message}, status=status)


class DashboardHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[DashboardRequestHandler],
        *,
        db_path: Path | None,
        config_dir: Path,
        state_dir: Path,
        quiet: bool,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.db_path = db_path
        self.config_dir = config_dir
        self.state_dir = state_dir
        self.quiet = quiet


def create_dashboard_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    db_path: Path | None = None,
    config_dir: Path = Path("configs/sources"),
    state_dir: Path = Path("local/state"),
    quiet: bool = False,
) -> DashboardHTTPServer:
    return DashboardHTTPServer(
        (host, port),
        partial(DashboardRequestHandler),
        db_path=db_path,
        config_dir=config_dir,
        state_dir=state_dir,
        quiet=quiet,
    )


def serve_dashboard(
    host: str = "127.0.0.1",
    port: int = 8765,
    db_path: Path | None = None,
    config_dir: Path = Path("configs/sources"),
    state_dir: Path = Path("local/state"),
    quiet: bool = False,
) -> None:
    server = create_dashboard_server(
        host=host,
        port=port,
        db_path=db_path,
        config_dir=config_dir,
        state_dir=state_dir,
        quiet=quiet,
    )
    url = f"http://{host}:{server.server_port}"
    print(f"Serving Policy Tracker dashboard at {url}")
    with server:
        server.serve_forever()
