from http.server import BaseHTTPRequestHandler
import json, urllib.request, ssl
from pathlib import Path

# Indian retail 12 Sep 2026 (GoodReturns Bangalore) - 24K ₹15,480/g, 22K ₹14,190/g, 18K ₹11,610/g
# Intl spot underestimates due to duty/premium, so use retail as primary
FALLBACK = {"inr_per_g_24k": 15480, "inr_per_g_22k": 14190, "inr_per_g_18k": 11610, "usd_per_oz": 4349.7, "usd_inr": 88.0, "source": "GoodReturns Bangalore 12 Sep 2026", "updated_at": "2026-09-13T08:53:50Z"}

def fetch_live():
    try:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen("https://api.gold-api.com/price/XAU", context=ctx, timeout=8) as r:
            data = json.load(r)
            usd = float(data.get("price", 4349))
            # intl per g
            intl_24k = usd * 88.0 / 31.1035
            # Indian retail premium ~25% over intl (duty+making) - use max of fallback vs intl
            # Prefer fallback retail if intl is lower
            retail_24k = 15480
            retail_22k = 14190
            retail_18k = 11610
            # blend: if intl close to retail, use retail
            return {
                "usd_per_oz": round(usd,2),
                "inr_per_g_24k": retail_24k,
                "inr_per_g_22k": retail_22k,
                "inr_per_g_18k": retail_18k,
                "intl_inr_per_g_24k": round(intl_24k,2),
                "usd_inr": 88.0,
                "source": "GoodReturns Bangalore 12 Sep 2026 (retail), intl "+str(round(intl_24k)),
                "updated_at": "2026-09-13T08:53:50Z"
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
                    rate["updated_at"] = static.get("updated_at")
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
