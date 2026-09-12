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
                text = p.read_text(encoding="utf-8")
                data = json.loads(text)
                # try to get last_updated from public/gold_rate.json or history, fallback to mtime
                last_updated = None
                try:
                    # try history snapshot
                    hist = Path(__file__).resolve().parent.parent / "public" / "gold_rate.json"
                    if hist.exists():
                        j = json.loads(hist.read_text())
                        last_updated = j.get("updated_at")
                except: pass
                if not last_updated:
                    try:
                        import time
                        mtime = p.stat().st_mtime
                        # if mtime is too old (2018), use now
                        if mtime < 1700000000:  # before 2023
                            raise ValueError("old mtime")
                        last_updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(mtime))
                    except:
                        import time as _t
                        last_updated = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
                return data, p.parent.name if p.parent.name != "api" else "output-full-15", last_updated
            except Exception as e:
                return [], f"Could not read {p}: {e}", None
    return [], "No ranked JSON found. Run the scraper first.", None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse
        parsed = urlparse(self.path)
        if parsed.path == "/api/products" or parsed.path == "/api/products.py":
            products, source, last_updated = latest_products()
            payload = json.dumps({"source": source, "products": products, "last_updated": last_updated}, ensure_ascii=False)
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
