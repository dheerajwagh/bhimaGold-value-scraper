"""Rank Bhima Gold products by gold value divided by grand total."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeoutError, async_playwright


CATEGORY_URL = "https://www.bhimagold.com/jewellery/gold"
PRODUCT_API_URL = "https://prod-apis.bhimagold.com/api/app/product/products"
ORG_ID = "1653277918007"
PRODUCT_PATH = "/products/"
MONEY_RE = re.compile(r"(?:₹|Rs\.?|INR)?\s*(\d[\d,]*(?:\.\d{1,2})?)", re.IGNORECASE)
GOLD_LABEL_RE = re.compile(r"\bgold\s*(?:\d{1,2}\s*k|\d{1,3}\s*kt)?\b", re.IGNORECASE)
TOTAL_LABEL_RE = re.compile(r"grand\s*total|total\s*amount|payable", re.IGNORECASE)


@dataclass
class Product:
    name: str
    url: str
    gold_value: float | None = None
    grand_total: float | None = None
    value_ratio: float | None = None
    error: str | None = None
    # extended fields from Product Details / Metal Details
    gross_weight: float | None = None
    metal_weight: float | None = None
    stone_weight: float | None = None
    length: str | None = None
    width: str | None = None
    thickness: str | None = None
    rate: float | None = None
    making_charges: float | None = None
    gst: float | None = None
    discount: float | None = None
    subtotal: float | None = None
    product_total: float | None = None


def parse_money_values(text: str) -> list[float]:
    values: list[float] = []
    for match in MONEY_RE.finditer(text.replace("\u00a0", " ")):
        value = float(match.group(1).replace(",", ""))
        if value >= 100:
            values.append(value)
    return values


def candidate_rows(soup: BeautifulSoup) -> Iterable[str]:
    elements = soup.select("tr, [role='row'], li, p")
    matching_rows = []
    for element in elements:
        text = " ".join(element.get_text(" ", strip=True).split())
        if text and (GOLD_LABEL_RE.search(text) or TOTAL_LABEL_RE.search(text)):
            matching_rows.append(text)
    if matching_rows:
        yield from matching_rows
        return
    for element in soup.select("div"):
        text = " ".join(element.get_text(" ", strip=True).split())
        if text and (GOLD_LABEL_RE.search(text) or TOTAL_LABEL_RE.search(text)):
            yield text


def extract_detail(soup: BeautifulSoup, label: str) -> str | None:
    # look for Product Details: label like "Gross weight:" or "Length:"
    for el in soup.select("tr, li, p, div"):
        txt = " ".join(el.get_text(" ", strip=True).split())
        if not txt:
            continue
        # case-insensitive label match with colon
        if re.search(rf"\b{re.escape(label)}\s*:", txt, re.I):
            # return value after colon
            parts = re.split(rf"{re.escape(label)}\s*:", txt, flags=re.I)
            if len(parts) > 1:
                val = parts[1].split("  ")[0].strip()
                # clean up trailing labels
                val = re.split(r"\s{2,}| \b[A-Z][a-z]+:", val)[0].strip()
                return val or None
    # fallback search in page text
    page_text = " ".join(soup.stripped_strings)
    m = re.search(rf"{re.escape(label)}\s*:\s*([^:]+?)(?:\s+[A-Z][a-z]+:|$)", page_text, re.I)
    if m:
        return m.group(1).strip().split("  ")[0]
    return None

def parse_weight_value(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([\d,.]+)\s*g", text, re.I)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except:
            return None
    m2 = re.search(r"([\d,.]+)", text)
    if m2:
        try:
            return float(m2.group(1).replace(",", ""))
        except:
            return None
    return None

def parse_product(html: str, url: str, fallback_name: str) -> Product:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("h1")
    name = title.get_text(" ", strip=True) if title else fallback_name
    rows = list(dict.fromkeys(candidate_rows(soup)))

    gold_candidates: list[float] = []
    total_candidates: list[float] = []
    for row in rows:
        values = parse_money_values(row)
        if re.search(r"\bgold\s+\d{1,2}\s*k(?:t)?\b", row, re.IGNORECASE):
            gold_candidates.extend(values)
        if TOTAL_LABEL_RE.search(row):
            total_candidates.extend(values)

    gold_value = gold_candidates[-1] if gold_candidates else None
    grand_total = total_candidates[-1] if total_candidates else None

    if gold_value is None or grand_total is None:
        page_text = " ".join(soup.stripped_strings)
        if gold_value is None:
            gold_match = re.search(r"gold.{0,100}?₹?\s*([\d,]+(?:\.\d{1,2})?)", page_text, re.IGNORECASE)
            if gold_match:
                gold_value = float(gold_match.group(1).replace(",", ""))
        if grand_total is None:
            total_match = re.search(r"grand\s*total.{0,100}?₹?\s*([\d,]+(?:\.\d{1,2})?)", page_text, re.IGNORECASE)
            if total_match:
                grand_total = float(total_match.group(1).replace(",", ""))

    # extended Product Details
    gross_weight = parse_weight_value(extract_detail(soup, "Gross weight"))
    metal_weight = parse_weight_value(extract_detail(soup, "Metal weight"))
    stone_weight = parse_weight_value(extract_detail(soup, "Stone weight"))
    length = extract_detail(soup, "Length")
    width = extract_detail(soup, "Width")
    thickness = extract_detail(soup, "Thickness")

    # Metal Details table - parse money values with labels
    page_text = " ".join(soup.stripped_strings)
    def find_money(label):
        m = re.search(rf"{label}.{{0,80}}?₹\s*([\d,]+(?:\.\d{{1,2}})?)", page_text, re.I)
        if m:
            try: return float(m.group(1).replace(",", ""))
            except: return None
        return None
    rate = find_money("Gold 22K")
    if rate is None:
        rate = find_money(r"Rate")
    making = find_money("Making Charges")
    gst = find_money(r"\bGST\b")
    discount = find_money("Discount")
    subtotal = find_money("Subtotal")
    product_total = find_money("Product Total")

    ratio = gold_value / grand_total if gold_value and grand_total else None
    error = None if ratio is not None else "Could not find both gold value and grand total"
    return Product(name, url, gold_value, grand_total, ratio, error,
                   gross_weight, metal_weight, stone_weight, length, width, thickness,
                   rate, making, gst, discount, subtotal, product_total)


async def discover_product_urls(page: Page, expected_count: int) -> list[tuple[str, str]]:
    response = await page.goto(CATEGORY_URL, wait_until="domcontentloaded", timeout=90_000)
    if response and response.status >= 400:
        body = (await page.locator("body").inner_text()).lower()
        if response.status == 403 and "cloudflare" in body:
            raise RuntimeError(
                "Bhima Gold returned a Cloudflare 403 block page. "
                "Run this from an allowed network or use a headed browser session."
            )
        raise RuntimeError(f"Category page returned HTTP {response.status}")

    found: dict[str, str] = {}
    page_number = 1
    api_count = expected_count
    while len(found) < min(expected_count, api_count):
        query = urllib.parse.urlencode(
            {
                "orgId": ORG_ID,
                "locale": "en-IN",
                "country": "en-IN",
                "pageNumber": str(page_number),
                "listSlug": "gold",
                "urlSlug": "gold",
            }
        )
        request = urllib.request.Request(
            f"{PRODUCT_API_URL}?{query}",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.load(response).get("data", {})
        except Exception:
            break
        api_count = int(data.get("count") or api_count)
        items = data.get("productList", [])
        for item in items:
            slug = item.get("slug")
            if slug:
                found[urljoin(CATEGORY_URL, f"/products/{slug}")] = item.get("title", slug)
        if not items:
            break
        page_number += 1

    if found:
        return list(found.items())[:expected_count]

    previous_count = 0
    stable_rounds = 0
    for _ in range(120):
        await page.mouse.wheel(0, 12_000)
        await page.wait_for_timeout(700)
        links = await page.locator(f'a[href*="{PRODUCT_PATH}"]').evaluate_all(
            "els => els.map(el => ({url: el.href, name: (el.innerText || el.textContent || '').trim()}))"
        )
        count = len({item["url"] for item in links})
        if count == previous_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
            previous_count = count
        if count >= expected_count or stable_rounds >= 8:
            break

    for item in await page.locator(f'a[href*="{PRODUCT_PATH}"]').evaluate_all(
        "els => els.map(el => ({url: el.href, name: (el.innerText || el.textContent || '').trim()}))"
    ):
        url = item["url"].split("#", 1)[0]
        if url.startswith("http") and PRODUCT_PATH in url:
            found[url] = " ".join(item["name"].split())
    return list(found.items())


async def scrape_products(
    browser: Browser,
    links: list[tuple[str, str]],
    concurrency: int,
    output_dir: Path,
    batch_size: int,
) -> list[Product]:
    results: list[Product | None] = [None] * len(links)
    work_queue: asyncio.Queue[tuple[int, str, str]] = asyncio.Queue()
    completed = 0
    for index, (url, name) in enumerate(links):
        work_queue.put_nowait((index, url, name))

    async def worker() -> None:
        nonlocal completed
        page = await browser.new_page()
        try:
            while True:
                try:
                    index, url, fallback_name = work_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                    await page.wait_for_timeout(500)
                    results[index] = parse_product(await page.content(), url, fallback_name)
                except Exception as exc:
                    results[index] = Product(
                        fallback_name,
                        url,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                finally:
                    work_queue.task_done()
                    completed += 1
                    if completed % batch_size == 0 or completed == len(links):
                        snapshot = [product for product in results if product is not None]
                        write_outputs(snapshot, output_dir)
                        write_checkpoint(snapshot, output_dir, len(links))
                        print(
                            f"Processed {completed}/{len(links)} products; "
                            f"valid ratios: {sum(product.value_ratio is not None for product in snapshot)}",
                            flush=True,
                        )
        finally:
            await page.close()

    workers = [asyncio.create_task(worker()) for _ in range(min(concurrency, len(links)))]
    await asyncio.gather(*workers)
    return [product for product in results if product is not None]


def write_outputs(products: list[Product], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ranked = sorted(products, key=lambda product: product.value_ratio or -1, reverse=True)
    fields = ["rank", "name", "url", "gold_value", "grand_total", "value_ratio", "error",
              "gross_weight", "metal_weight", "stone_weight", "length", "width", "thickness",
              "rate", "making_charges", "gst", "discount", "subtotal", "product_total"]
    with (output_dir / "bhima_gold_ranked.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for rank, product in enumerate(ranked, 1):
            row = asdict(product)
            row["rank"] = rank
            writer.writerow({field: row[field] for field in fields})
    (output_dir / "bhima_gold_ranked.json").write_text(
        json.dumps([asdict(product) for product in ranked], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_checkpoint(products: list[Product], output_dir: Path, total: int) -> None:
    (output_dir / "bhima_gold_checkpoint.json").write_text(
        json.dumps(
            {"total": total, "completed": len(products), "products": [asdict(product) for product in products]},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_checkpoint(output_dir: Path) -> list[Product]:
    checkpoint = output_dir / "bhima_gold_checkpoint.json"
    if not checkpoint.exists():
        return []
    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    return [Product(**item) for item in data.get("products", [])]


async def run(
    expected_count: int,
    concurrency: int,
    output_dir: Path,
    headed: bool,
    user_data_dir: Path,
    cdp_url: str | None,
    batch_size: int,
    resume: bool,
) -> None:
    async with async_playwright() as playwright:
        if cdp_url:
            browser = await playwright.chromium.connect_over_cdp(cdp_url)
            owns_browser = False
        else:
            browser = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                channel="chrome",
                headless=not headed,
            )
            owns_browser = True
        category_page = await browser.new_page()
        try:
            links = await discover_product_urls(category_page, expected_count)
        finally:
            await category_page.close()
        print(f"Discovered {len(links)} product links")
        existing = load_checkpoint(output_dir) if resume else []
        completed_urls = {product.url for product in existing}
        pending_links = [(url, name) for url, name in links if url not in completed_urls]
        if existing:
            print(f"Resuming from checkpoint: {len(existing)} products already processed", flush=True)
        products = await scrape_products(browser, pending_links, concurrency, output_dir, batch_size)
        products = existing + products
        if owns_browser:
            await browser.close()
    write_outputs(products, output_dir)
    write_checkpoint(products, output_dir, len(links))
    parsed = sum(product.value_ratio is not None for product in products)
    print(f"Parsed {parsed}/{len(products)} products")
    print(f"Wrote {output_dir / 'bhima_gold_ranked.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-count", type=int, default=3295)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=100, help="Save and sort progress after this many products")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--headed", action="store_true", help="Show Chromium while scraping")
    parser.add_argument(
        "--user-data-dir",
        type=Path,
        default=Path(".browser-profile"),
        help="Persistent Chrome profile used for cookies and browser checks",
    )
    parser.add_argument(
        "--cdp-url",
        default=None,
        help="Attach to an already-running Chrome, for example http://127.0.0.1:9222",
    )
    parser.add_argument("--resume", action="store_true", help="Continue from the output directory checkpoint")
    args = parser.parse_args()
    asyncio.run(
        run(
            args.expected_count,
            args.concurrency,
            args.output_dir,
            args.headed,
            args.user_data_dir,
            args.cdp_url,
            args.batch_size,
            args.resume,
        )
    )


if __name__ == "__main__":
    main()