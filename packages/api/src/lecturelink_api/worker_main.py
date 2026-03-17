"""Worker entrypoint — runs arq worker + minimal health server for Cloud Run.

Usage:
    python -m lecturelink_api.worker_main              # all queues (dev)
    python -m lecturelink_api.worker_main --queue fast  # fast queue only
    python -m lecturelink_api.worker_main --queue slow  # slow queue only
"""

from __future__ import annotations

import os
import sys
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


_WORKER_SETTINGS = {
    "fast": "lecturelink_api.worker.FastWorkerSettings",
    "slow": "lecturelink_api.worker.SlowWorkerSettings",
    "all": "lecturelink_api.worker.WorkerSettings",
}

if __name__ == "__main__":
    # Parse --queue argument
    queue = os.environ.get("WORKER_QUEUE", "all")
    if "--queue" in sys.argv:
        idx = sys.argv.index("--queue")
        if idx + 1 < len(sys.argv):
            queue = sys.argv[idx + 1]

    settings_path = _WORKER_SETTINGS.get(queue, _WORKER_SETTINGS["all"])

    # Start health server in background thread
    t = threading.Thread(target=_start_health_server, daemon=True)
    t.start()

    # Run arq worker in main thread
    from arq.cli import cli

    sys.argv = ["arq", settings_path]
    cli()
