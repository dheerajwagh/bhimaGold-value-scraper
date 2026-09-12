from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path

# Try multiple locations: bundled copy in api/, then root output dirs
CANDIDATES = [
    Path(__file__).parent / "bhima_gold_ranked.json",
    Path(__file__).resolve().parent.parent / "output-full-15" / "bhima_gold_ranked.json",
    Path(__file__).resolve().parent.parent / "output-full" / "bhima_gold_ranked.json",
]

def latest_products():
    # Prefer bundled copy
    for p in CANDIDATES:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return data, p.parent.name if p.parent.name != "api" else "output-full-15"
            except Exception as e:
                return [], f"Could not read {p}: {e}"
    return [], "No ranked JSON found. Run the scraper first."

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse
        parsed = urlparse(self.path)
        if parsed.path == "/api/products" or parsed.path == "/api/products.py":
            products, source = latest_products()
            payload = json.dumps({"source": source, "products": products}, ensure_ascii=False)
            body = payload.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"not found"}')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
