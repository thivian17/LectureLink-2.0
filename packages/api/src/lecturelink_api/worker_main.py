"""Worker entrypoint — runs arq worker + minimal health server for Cloud Run."""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass  # suppress access logs


def _start_health_server():
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()


if __name__ == "__main__":
    # Start health server in background thread
    t = threading.Thread(target=_start_health_server, daemon=True)
    t.start()

    # Run arq worker in main thread
    import sys

    from arq.cli import cli

    sys.argv = ["arq", "lecturelink_api.worker.WorkerSettings"]
    cli()
