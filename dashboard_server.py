from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent
DATA_DIRS = [ROOT / "output-full-15", ROOT / "output-full", ROOT / "output"]
DASHBOARD_DIR = ROOT / "dashboard"


def latest_products() -> tuple[list[dict], str]:
    candidates = [directory / "bhima_gold_ranked.json" for directory in DATA_DIRS]
    candidates = [path for path in candidates if path.exists()]
    if not candidates:
        return [], "No ranked JSON found. Run the scraper first."
    source = max(candidates, key=lambda path: path.stat().st_mtime)
    try:
        return json.loads(source.read_text(encoding="utf-8")), source.parent.name
    except (OSError, json.JSONDecodeError) as error:
        return [], f"Could not read {source}: {error}"


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        if urlparse(self.path).path == "/api/products":
            products, source = latest_products()
            payload = json.dumps({"source": source, "products": products}, ensure_ascii=False)
            body = payload.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="Serve the Bhima Gold ranking dashboard")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), DashboardHandler)
    print(f"Dashboard: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
