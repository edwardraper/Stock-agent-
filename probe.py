#!/usr/bin/env python3
"""Diagnostic probe: dump how a store's product page exposes sizes,
colors and stock, so a checker can be written against it.

Prints (for the URL in PROBE_URL):
  - the Shopify /products/<handle>.json payload, if that endpoint exists
  - any ld+json blocks (Product / ProductGroup carry real availability)
  - option/variant names and availability
  - links to sibling product pages (colors are sometimes separate products)

Run via .github/workflows/probe.yml, which has real internet access.
"""
import json
import os
import re
import sys
from urllib.parse import urlparse

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


def get(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    print(f"GET {url} -> {resp.status_code} ({len(resp.content)} bytes)")
    return resp


def probe_json_endpoint(url):
    base = url.split("?")[0].rstrip("/")
    print("\n=== .json endpoint ===")
    try:
        resp = get(base + ".json")
    except requests.RequestException as exc:
        print("request failed:", exc)
        return
    if resp.status_code != 200:
        print("not available")
        return
    try:
        product = resp.json()["product"]
    except (ValueError, KeyError) as exc:
        print("unexpected payload:", exc)
        print(resp.text[:500])
        return
    print("title:", product.get("title"))
    print("options:", json.dumps(product.get("options"), ensure_ascii=False))
    for v in product.get("variants", []):
        print(
            "  variant:", v.get("id"), "|", v.get("title"),
            "| o1=", v.get("option1"), "o2=", v.get("option2"), "o3=", v.get("option3"),
            "| available=", v.get("available"),
        )


def probe_ld_json(html):
    print("\n=== ld+json blocks ===")
    found = False
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL
    ):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print("(unparseable block, first 300 chars)", raw[:300])
            continue
        blocks = data if isinstance(data, list) else [data]
        for block in blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("@type")
            print(f"\n-- @type={btype} --")
            if btype in ("Product", "ProductGroup"):
                found = True
                print("name:", block.get("name"))
                offers = block.get("offers")
                if isinstance(offers, dict):
                    offers = [offers]
                for offer in offers or []:
                    print("  offer:", offer.get("availability"), offer.get("sku"), offer.get("url"))
                for variant in block.get("hasVariant", []) or []:
                    offer = variant.get("offers", {}) or {}
                    if isinstance(offer, list):
                        offer = offer[0] if offer else {}
                    print(
                        "  variant:", variant.get("name"),
                        "| size=", variant.get("size"),
                        "| color=", variant.get("color"),
                        "| avail=", offer.get("availability"),
                        "| url=", offer.get("url"),
                    )
    if not found:
        print("(no Product/ProductGroup ld+json found)")


def probe_inline_json(html):
    """Shopify themes often inline the full variant list in a script tag."""
    print("\n=== inline variant JSON candidates ===")
    for pat, label in [
        (r'<script[^>]*id="ProductJson[^"]*"[^>]*>(.*?)</script>', "ProductJson"),
        (r'<script[^>]*data-product-json[^>]*>(.*?)</script>', "data-product-json"),
        (r'"variants"\s*:\s*(\[.{0,4000}?\])', "inline variants array"),
    ]:
        for m in re.finditer(pat, html, re.DOTALL):
            print(f"\n-- {label} (first 2500 chars) --")
            print(m.group(1).strip()[:2500])
            break


def probe_size_hints(html):
    print("\n=== size / availability markup hints ===")
    for kw in ("sold out", "sold-out", "out of stock", "outofstock", "unavailable",
               "notify me", "back in stock", "InStock"):
        n = len(re.findall(re.escape(kw), html, re.IGNORECASE))
        if n:
            print(f"  {kw!r}: {n} occurrences")

    print("\n-- inputs/options mentioning collar or size --")
    seen = set()
    for m in re.finditer(r"<(?:option|input|label|button)[^>]*>", html, re.IGNORECASE):
        tag = m.group(0)
        if re.search(r"1[4-8](\.5)?|size|collar", tag, re.IGNORECASE):
            key = tag[:200]
            if key not in seen:
                seen.add(key)
                print("   ", key)
            if len(seen) >= 40:
                return


def probe_siblings(html, url):
    print("\n=== sibling product links (possible colorways) ===")
    host = urlparse(url).netloc
    handles = sorted(set(re.findall(r'href="((?:https://' + re.escape(host) + r')?/[^"]*?/products/[^"?#]+)"', html)))
    for h in handles[:40]:
        print("   ", h)
    print(f"({len(handles)} unique product links)")


def main():
    url = os.environ.get("PROBE_URL")
    if not url:
        print("PROBE_URL not set", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("PROBING:", url)
    print("=" * 70)

    probe_json_endpoint(url)

    print("\n=== product page HTML ===")
    try:
        resp = get(url)
    except requests.RequestException as exc:
        print("request failed:", exc)
        sys.exit(1)
    if resp.status_code != 200:
        print("non-200; body starts:", resp.text[:500])
        sys.exit(1)
    html = resp.text

    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL)
    print("page title:", title.group(1).strip() if title else None)

    probe_ld_json(html)
    probe_inline_json(html)
    probe_size_hints(html)
    probe_siblings(html, url)


if __name__ == "__main__":
    main()
