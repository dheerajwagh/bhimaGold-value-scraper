from http.server import BaseHTTPRequestHandler
import json, urllib.request, ssl
from pathlib import Path

# fallback static
FALLBACK = {"inr_per_g_24k": 12306.45, "inr_per_g_22k": 11272.71, "inr_per_g_18k": 9229.84, "usd_per_oz": 4349.7, "usd_inr": 88.0, "source": "fallback"}

def fetch_live():
    try:
        # use unverified ssl to avoid cert issues
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen("https://api.gold-api.com/price/XAU", context=ctx, timeout=8) as r:
            data = json.load(r)
            usd = float(data.get("price", 4349))
            inr_per_g_24k = usd * 88.0 / 31.1035
            return {
                "usd_per_oz": round(usd,2),
                "inr_per_g_24k": round(inr_per_g_24k,2),
                "inr_per_g_22k": round(inr_per_g_24k*0.916,2),
                "inr_per_g_18k": round(inr_per_g_24k*0.75,2),
                "usd_inr": 88.0,
                "source": "gold-api.com"
            }
    except Exception as e:
        return {**FALLBACK, "error": str(e)}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse
        if self.path.startswith("/api/gold-rate"):
            rate = fetch_live()
            # also try to read static file if exists for history
            try:
                p = Path(__file__).parent.parent / "public" / "gold_rate.json"
                if p.exists():
                    static = json.loads(p.read_text())
                    # merge updated_at if present
                    rate["updated_at_static"] = static.get("updated_at")
            except: pass
            body = json.dumps(rate).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "public, max-age=300")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b'{"error":"not found"}')
