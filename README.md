# Stock Agent

Watches specific product variants on Shopify stores and sends a push
notification the moment one comes back in stock.

**Currently watching** (see `products.json`) — Thomas Pink formal shirts,
**16" collar**, in all three colourways:

| Product | Size watched |
| --- | --- |
| White Classic Fit Poplin Double Cuff | 16.0 |
| Pale Blue/White Gingham Cutaway Double Cuff | 16.0 |
| Blue/White Panama Stripe Double Cuff | 16.0 |

These shirts also have a **Sleeve length** option (Regular / Long). The
config doesn't constrain it, so *both* sleeve lengths are watched at 16"
and the notification says which one restocked.

## Configuring what to watch

Everything lives in `products.json` — no code changes needed to add,
remove or re-target products:

```json
{
  "ntfy_topic": "hoodie-restock-a1eb6a932d",
  "products": [
    {
      "name": "Friendly name used in notifications",
      "url": "https://<store>/products/<handle>",
      "match": { "Size": ["16.0"] }
    }
  ]
}
```

`match` maps an option name to the values you want. Any option you
*don't* list is left unconstrained, so `{"Size": ["16.0"]}` watches every
sleeve length / fit at that size. Option names must match the store's own
spelling exactly (here: `Size`, `Sleeve length`) — if they don't, the run
prints a loud `WARNING: no variants matched`.

## How stock is read

Stock comes from Shopify's `/products/<handle>.js` endpoint, which returns
a real `available` boolean per variant.

⚠️ The sibling `.json` endpoint is **not** a substitute — on both stores
tried so far it reports `"available": null` for every variant, which looks
exactly like "permanently out of stock" and would mean the alert never
fires. This bit the original hoodie version of this project; `.js` is the
one to use.

If a store can't be read at all, the run fails loudly rather than
skipping, so a silent outage can't masquerade as "nothing restocked".

## Workflows

- **`stock-check.yml`** — every 30 minutes. Diffs against `state.json`
  (committed back after each run) and notifies on any out-of-stock →
  in-stock transition.
- **`health-check.yml`** — Mondays and Thursdays at 5pm UK time. Reports current status
  either way, so you have a heartbeat proving the checker still runs.
- **`probe.yml`** — manual. Takes any product URL and dumps how that store
  exposes options, variants and availability (`.json`/`.js` endpoints,
  ld+json, size dropdowns, sibling product links). Run this first when
  pointing the agent at a new store.

All three can be run by hand from the Actions tab. `stock-check` also
accepts:

- `debug` — log every matched variant and its availability.
- `test_message` — send arbitrary text as a notification, skipping the
  stock check entirely.
- `simulate_restock` — scan the real products but send the genuine
  restock alert as if everything were in stock. Useful for seeing exactly
  what the real alert looks like. It deliberately leaves `state.json`
  untouched: writing "everything in stock" would make a later real
  restock look like no change and silently suppress the actual alert.

## Notifications

Sent via [ntfy.sh](https://ntfy.sh) to the topic in `products.json`.
Subscribe in the ntfy app ([iOS](https://apps.apple.com/app/ntfy/id1625396347)
/ [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy))
or at <https://ntfy.sh/app>:

```
hoodie-restock-a1eb6a932d
```

(The topic name is historical — it carries the shirt alerts now too, so
there's nothing to re-subscribe to. ntfy topics are public-by-name, hence
the random suffix; don't post it anywhere public.)

## Adjusting later

- **Check frequency** — cron in `stock-check.yml` (`*/30 * * * *`).
  GitHub Actions won't reliably do intervals under ~5 minutes.
- **Status check-in time** — cron in `health-check.yml` (`0 16 * * 1,4`
  = Mon & Thu 5pm UK while on BST; becomes 4pm when the clocks go back,
  so change it to `0 17 * * 1,4` then).
- **Pausing** — comment out the `schedule:` block in either workflow; the
  manual trigger keeps working.
- **A store that isn't Shopify** — `fetch_variants()` is the only piece
  tied to Shopify. Run `probe.yml` against the new URL first; expect to
  adapt that one function.
