#!/usr/bin/env python3
"""Watch specific product variants on Shopify stores and push an ntfy.sh
notification the moment one goes from out-of-stock to in-stock.

What to watch lives in products.json: each entry gives a product URL and a
`match` filter of option name -> accepted values (e.g. {"Size": ["16.0"]}).
Options you don't list are left unconstrained, so a shirt matched only on
Size is watched in every sleeve length.

Stock comes from Shopify's /products/<handle>.js endpoint, which returns
a real `available` boolean per variant. Note the sibling `.json` endpoint
is NOT a substitute: on both stores tried so far it reports `available:
null` for every variant, which silently looks like "everything is out of
stock" forever.

Modes (env vars):
  TEST_MESSAGE=...   send that text as a notification and exit
  HEALTH_CHECK=1     scan and report current status, without diffing
  DEBUG=1            print every matched variant and its availability
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).parent
CONFIG_FILE = HERE / "products.json"
STATE_FILE = HERE / "state.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "application/json,text/javascript,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
DEBUG = os.environ.get("DEBUG", "").lower() not in ("", "false", "0")


def load_config():
    config = json.loads(CONFIG_FILE.read_text())
    topic = os.environ.get("NTFY_TOPIC") or config["ntfy_topic"]
    return topic, config["products"]


def fetch_variants(url):
    """Return (product_title, [variant dicts]) from the Shopify .js endpoint."""
    endpoint = url.split("?")[0].rstrip("/") + ".js"
    resp = requests.get(endpoint, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("title") or url, data.get("options") or [], data.get("variants") or []


def variant_options(variant, options):
    """Map option name -> this variant's value for it."""
    values = {}
    for index, option in enumerate(options):
        name = option["name"] if isinstance(option, dict) else str(option)
        values[name] = variant.get(f"option{index + 1}")
    return values


def matches(values, wanted):
    for name, accepted in wanted.items():
        if str(values.get(name)) not in [str(a) for a in accepted]:
            return False
    return True


def scan():
    """Return {key: {...}} for every variant we're watching."""
    _, products = load_config()
    watched = {}

    for product in products:
        url = product["url"]
        wanted = product.get("match", {})
        try:
            title, options, variants = fetch_variants(url)
        except (requests.RequestException, ValueError) as exc:
            # Reported loudly: a silent skip here would look identical to
            # "nothing restocked" and could hide an outage indefinitely.
            print(f"ERROR: could not read {url}: {exc}", file=sys.stderr)
            raise

        found = 0
        for variant in variants:
            values = variant_options(variant, options)
            if not matches(values, wanted):
                continue
            found += 1
            label = " / ".join(
                f"{name} {value}" for name, value in values.items() if value
            )
            watched[f"{url}|{variant['id']}"] = {
                "product": product.get("name") or title,
                "label": label,
                "available": bool(variant.get("available")),
                "url": f"{url}?variant={variant['id']}",
            }
            if DEBUG:
                print(f"debug: {product.get('name')} | {label} -> available={variant.get('available')}")

        if not found:
            print(
                f"WARNING: no variants matched {wanted} for {url} — "
                "the store may have renamed its options.",
                file=sys.stderr,
            )

    return watched


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(watched):
    state = {key: info["available"] for key, info in watched.items()}
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def notify(title, message, topic):
    resp = requests.post(
        f"https://ntfy.sh/{topic}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Priority": "high", "Tags": "shirt"},
        timeout=15,
    )
    resp.raise_for_status()


def describe(info):
    return f"{info['product']} — {info['label']}"


def run_check(topic):
    watched = scan()
    previous = load_state()

    restocked = [
        key for key, info in watched.items()
        if info["available"] and not previous.get(key, False)
    ]

    if restocked:
        lines = [f"{describe(watched[k])}\n{watched[k]['url']}" for k in restocked]
        notify("Back in stock!", "\n\n".join(lines), topic)
        print("Notified restock for:", "; ".join(describe(watched[k]) for k in restocked))
    else:
        in_stock = [describe(i) for i in watched.values() if i["available"]]
        print(f"No new restocks. {len(watched)} variants watched; in stock now: {in_stock or 'none'}")

    save_state(watched)


def run_health_check(topic):
    watched = scan()
    in_stock = [describe(i) for i in watched.values() if i["available"]]

    if in_stock:
        body = "Currently IN STOCK:\n" + "\n".join(in_stock)
    else:
        body = f"All {len(watched)} watched variants are out of stock."

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    notify("Stock agent daily check-in", f"Checker ran successfully at {stamp}.\n{body}", topic)
    print("Sent daily health check:", body)


def main():
    topic, _ = load_config()

    test_message = os.environ.get("TEST_MESSAGE")
    if test_message:
        notify("Stock Agent Test", test_message, topic)
        print("Sent test notification:", test_message)
        return

    if os.environ.get("HEALTH_CHECK", "").lower() not in ("", "false", "0"):
        run_health_check(topic)
        return

    run_check(topic)


if __name__ == "__main__":
    main()
