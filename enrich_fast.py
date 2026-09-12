import json, subprocess, re, time
from pathlib import Path
ROOT = Path(__file__).parent
INPUT = ROOT/"output-full-15"/"bhima_gold_ranked.json"
def curl_json(url):
    try:
        out = subprocess.check_output(["curl","-s","--max-time","8",url], timeout=10)
        return json.loads(out)
    except: return None

# Indian retail 12 Sep 2026 - use retail rates, not intl spot (intl underestimates)
rate_live = curl_json("https://api.gold-api.com/price/XAU")
usd_per_oz = float(rate_live["price"]) if rate_live and "price" in rate_live else 4349.7
rate_info = {
    "usd_per_oz": round(usd_per_oz,2),
    "inr_per_g_24k": 15480,
    "inr_per_g_22k": 14190,
    "inr_per_g_18k": 11610,
    "intl_inr_per_g_24k": round(usd_per_oz*88.0/31.1035,2),
    "usd_inr": 88.0,
    "source": "GoodReturns Bangalore 12 Sep 2026 (retail)",
    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
}
print(f"rate {rate_info}")

data = json.loads(INPUT.read_text())
print(f"loaded {len(data)}")

def purity_factor(name):
    m=re.search(r"\b(18|22|24)\s*kt", name, re.I)
    return { "18":0.75, "22":0.916, "24":1.0 }.get(m.group(1),0.916) if m else 0.916

enriched=[]
for p in data:
    name=p["name"]
    gv=p.get("gold_value")
    gt=p.get("grand_total")
    making=None; making_pct=None; weight=None; discount=None; discount_pct=None
    if gv and gt:
        making=round(gt-gv,2)
        making_pct=round(making/gt*100,2) if gt else None
        # weight proxy
        if "18" in name:
            r=rate_info["inr_per_g_18k"]
        elif "24" in name:
            r=rate_info["inr_per_g_24k"]
        else:
            r=rate_info["inr_per_g_22k"]
        try: weight=round(float(gv)/float(r),2)
        except: pass
    # purity
    m=re.search(r"\b(18|22|24)\s*kt", name, re.I)
    purity=f"{m.group(1)}KT" if m else "Other"
    lname=name.lower()
    if "baby" in lname or "kids" in lname: audience="Kids"
    elif "women" in lname: audience="Women"
    elif "unisex" in lname: audience="Unisex"
    elif " men" in lname or lname.startswith("men ") or "for men" in lname: audience="Men"
    else: audience="Unisex/Other"
    # category from existing heuristic + keep API category null for now
    terms=['necklace','chain','bangle','ring','earring','stud','drops','mangalsutra','haar am','haaram','pendant','bracelet','coin','anklet','nosepin']
    found=next((t for t in terms if t in lname), None)
    cat="Haaram" if found=="haar am" else found.capitalize() if found else "Other"
    enriched.append({**p, "making_charges_proxy": making, "making_pct": making_pct, "weight_proxy_g": weight, "purity": purity, "audience": audience, "category_api": cat, "image": None, "price_api": None, "special_price_api": None, "discount_amount": None, "discount_pct": None})

# write
out = ROOT/"output-full-15"/"bhima_gold_ranked.json"
backup = ROOT/"output-full-15"/"bhima_gold_ranked.backup.json"
if not backup.exists():
    backup.write_text(json.dumps(data, indent=2, ensure_ascii=False))
out.write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
print(f"wrote {out}")
Path(ROOT/"api"/"bhima_gold_ranked.json").write_text(json.dumps(enriched, indent=2, ensure_ascii=False))
print("copied to api")
# history
hist_dir=ROOT/"history"
hist_dir.mkdir(exist_ok=True)
hist=hist_dir/f"bhima_gold_{time.strftime('%Y-%m-%d')}.json"
hist.write_text(json.dumps({"snapshot_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "gold_rate": rate_info, "products": enriched}, indent=2))
print(f"history {hist}")
# gold rate for ticker
Path(ROOT/"public"/"gold_rate.json").write_text(json.dumps(rate_info, indent=2))
print("gold_rate.json")
print("sample", enriched[0])
