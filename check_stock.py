#!/usr/bin/env python3
"""Check per-color, per-size stock for the Union Kingdom Clothing polar
fleece hoodie and push an ntfy.sh notification whenever any color/size
combination transitions from out-of-stock to in-stock.

On this store, colors are separate Shopify products linked via swatch
links on the product page (not variants of a single product), and the
Shopify /products/<handle>.json endpoint doesn't expose live inventory
(its "available" field is always null). Real stock status instead lives
in each page's embedded ProductGroup ld+json block, so this scrapes that.

Run standalone (state persisted in state.json) or via the scheduled
GitHub Actions workflow in .github/workflows/stock-check.yml.
"""
import json
import os
import re
import sys
from pathlib import Path

import requests

STORE = "https://unionkingdomclo.com"
BASE_HANDLE = "double-layer-polar-fleece-hoodie"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "hoodie-restock-a1eb6a932d")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
STATE_FILE = Path(__file__).parent / "state.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockAgent/1.0)"}
DEBUG = bool(os.environ.get("DEBUG"))


def fetch_html(handle):
    resp = requests.get(f"{STORE}/products/{handle}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def discover_color_handles(base_html):
    handles = set(re.findall(
        r'class="product-swatch-link[^"]*"\s+href="/products/([a-z0-9\-]+)"', base_html
    ))
    handles.add(BASE_HANDLE)
    return sorted(handles)


def extract_product_group(html):
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if data.get("@type") == "ProductGroup":
            return data
    return None


def color_name_from_title(name):
    m = re.search(r"'([^']+)'", name or "")
    return m.group(1) if m else (name or "Unknown")


def stock_for_handle(handle):
    html = fetch_html(handle)
    group = extract_product_group(html)
    if not group:
        print(f"warning: no ProductGroup data found for {handle}", file=sys.stderr)
        return None, {}

    color = color_name_from_title(group.get("name", handle))
    sizes = {}
    for variant in group.get("hasVariant", []):
        size = variant.get("name", "").rsplit(" - ", 1)[-1].strip()
        offer = variant.get("offers", {})
        available = "instock" in offer.get("availability", "").lower()
        url = offer.get("url", f"{STORE}/products/{handle}")
        sizes[size] = {"available": available, "url": url}

    if DEBUG:
        print(f"debug: {handle} -> color={color!r} sizes={ {s: v['available'] for s, v in sizes.items()} }")

    return color, sizes


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def notify(title, message):
    try:
        requests.post(
            NTFY_URL,
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "high", "Tags": "shirt"},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"Failed to send notification: {exc}", file=sys.stderr)


def main():
    test_message = os.environ.get("TEST_MESSAGE")
    if test_message:
        notify("Stock Agent Test", test_message)
        print("Sent test notification:", test_message)
        return

    base_html = fetch_html(BASE_HANDLE)
    handles = discover_color_handles(base_html)
    print("Tracking color product handles:", handles)

    previous = load_state()
    current = {}
    details = {}

    for handle in handles:
        try:
            color, sizes = stock_for_handle(handle)
        except requests.RequestException as exc:
            print(f"warning: failed to fetch {handle}: {exc}", file=sys.stderr)
            continue
        if color is None:
            continue
        for size, info in sizes.items():
            key = f"{handle}|{size}"
            current[key] = info["available"]
            details[key] = {"color": color, "size": size, "url": info["url"]}

    restocked = [
        key for key, available in current.items()
        if available and not previous.get(key, False)
    ]

    if restocked:
        lines = [
            f"{details[key]['color']} ({details[key]['size']}): {details[key]['url']}"
            for key in restocked
        ]
        notify(
            "Hoodie back in stock!",
            "Union Kingdom polar fleece hoodie restocked:\n" + "\n".join(lines),
        )
        print("Notified restock for:", ", ".join(f"{details[k]['color']} {details[k]['size']}" for k in restocked))
    else:
        summary = {f"{details[k]['color']} {details[k]['size']}": v for k, v in current.items()}
        print("No new restocks. Current status:", summary)

    save_state(current)


if __name__ == "__main__":
    main()
