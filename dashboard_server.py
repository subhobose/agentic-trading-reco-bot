from __future__ import annotations

import http.server
import os
import socketserver
from pathlib import Path


def run_dashboard_server(port: int = 8765) -> None:
    base = Path(__file__).resolve().parent
    os.chdir(base)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"[dashboard] Serving at http://127.0.0.1:{port}/dashboard/")
        httpd.serve_forever()


if __name__ == "__main__":
    run_dashboard_server()

