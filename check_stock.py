#!/usr/bin/env python3
"""Check per-color stock for the Union Kingdom Clothing double-layer polar
fleece hoodie and push an ntfy.sh notification whenever a color transitions
from out-of-stock to in-stock.

Run standalone (state persisted in state.json) or via the scheduled
GitHub Actions workflow in .github/workflows/stock-check.yml.
"""
import json
import os
import re
import sys
from pathlib import Path

import requests

PRODUCT_URL = "https://unionkingdomclo.com/products/double-layer-polar-fleece-hoodie.json"
PRODUCT_PAGE = "https://unionkingdomclo.com/products/double-layer-polar-fleece-hoodie"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "hoodie-restock-a1eb6a932d")
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"
STATE_FILE = Path(__file__).parent / "state.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; StockAgent/1.0)"}


def fetch_product():
    resp = requests.get(PRODUCT_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()["product"]


def color_option_index(product):
    for i, opt in enumerate(product["options"]):
        if opt["name"].strip().lower() in ("color", "colour"):
            return i
    return 0


def stock_by_color(product):
    idx = color_option_index(product)
    key = f"option{idx + 1}"
    colors = {}
    variant_for_color = {}
    for variant in product["variants"]:
        color = variant.get(key) or variant["title"]
        available = bool(variant.get("available"))
        colors[color] = colors.get(color, False) or available
        if available and color not in variant_for_color:
            variant_for_color[color] = variant["id"]
    return colors, variant_for_color


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
    product = fetch_product()

    if os.environ.get("DEBUG_DUMP"):
        print("options:", product["options"])
        print("first variant raw:", json.dumps(product["variants"][0], indent=2))

    if os.environ.get("DEBUG_HTML"):
        html_resp = requests.get(PRODUCT_PAGE, headers=HEADERS, timeout=30)
        html = html_resp.text
        print("HTML status:", html_resp.status_code, "length:", len(html))
        for m in re.finditer(r"color", html, re.IGNORECASE):
            start = max(0, m.start() - 80)
            print("color ctx:", html[start:m.start() + 80].replace("\n", " "))
        handles = sorted(set(re.findall(r"/products/([a-z0-9\-]+)", html)))
        print("linked product handles:", handles)
        for h in handles:
            idx = html.find(f"/products/{h}")
            print(f"--- context for {h} ---")
            print(html[max(0, idx - 400):idx + 100].replace("\n", " "))
        title_m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
        print("page title:", title_m.group(1) if title_m else None)
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
            print("ld+json:", m.group(1)[:3000])

    current, variant_for_color = stock_by_color(product)
    previous = load_state()

    restocked = [
        color
        for color, available in current.items()
        if available and not previous.get(color, False)
    ]

    if restocked:
        lines = []
        for color in restocked:
            vid = variant_for_color.get(color)
            link = f"{PRODUCT_PAGE}?variant={vid}" if vid else PRODUCT_PAGE
            lines.append(f"{color}: {link}")
        notify(
            "Hoodie back in stock!",
            "Double Layer Polar Fleece Hoodie is back in stock:\n" + "\n".join(lines),
        )
        print("Notified restock for:", ", ".join(restocked))
    else:
        print("No new restocks. Current status:", current)

    save_state(current)


if __name__ == "__main__":
    main()
