# Stock Agent

Watches the [Double Layer Polar Fleece Hoodie](https://unionkingdomclo.com/products/double-layer-polar-fleece-hoodie)
on unionkingdomclo.com, in every color, and sends you a push notification
the moment any color/size comes back in stock.

> **Status: PAUSED.** The hoodie watch is finished, so both workflows have
> their `schedule:` triggers commented out — nothing runs automatically
> and no notifications are sent. All the code is kept intact and is ready
> to be pointed at other products. Uncomment the `schedule:` block in
> either workflow to resume, or run either one manually from the Actions
> tab at any time.

## How it works

On this store, colors aren't Shopify variants of one product — each color
is a **separate product**, cross-linked by swatch buttons on the product
page. The store also hides live inventory from the standard
`/products/<handle>.json` endpoint (its `available` field is always
`null`). Real stock status lives in a `ProductGroup` block the theme
embeds as `ld+json` on each product page instead.

So `check_stock.py`:

1. Fetches the base product page (`double-layer-polar-fleece-hoodie`,
   currently "Flower Gray") and scrapes its color-swatch links to find
   every sibling color product. As of this writing that's Flower Gray,
   Green, Navy Blue, and Black — discovered dynamically each run, so new
   colors the store adds get picked up automatically.
2. Fetches each color's product page and parses its `ProductGroup`
   ld+json for real per-size availability (`InStock` / `OutOfStock`).
3. Diffs the result against `state.json` (last known state, committed
   back to the repo after every run, keyed by `handle|size`).
4. Any color/size that flips from out-of-stock to in-stock triggers a
   push notification via [ntfy.sh](https://ntfy.sh) with a direct link to
   buy that variant.

`.github/workflows/stock-check.yml` ran this on a GitHub Actions schedule
(every 30 minutes) and can still be triggered manually.

`.github/workflows/health-check.yml` ran a separate daily job (9am UK
time) that does a real scan of every color/size and sends a status ntfy
notification either way — "all sold out" or a list of what's in stock —
so you have a heartbeat confirming the checker is actually running, not
just silently failing.

Both schedules are currently commented out (see Status above).

## Reusing this for other products

The notification plumbing (`notify()`, the ntfy topic, the state-diffing
in `run_check()`, the daily heartbeat, and both workflows) is generic and
carries over to any product. What is **not** generic is how stock gets
read: `discover_color_handles()` and `extract_product_group()` are
tailored to this specific Shopify theme — colors as separate cross-linked
products, and availability in an embedded `ProductGroup` ld+json block.

For a new store, expect to re-check that part first (this took several
live debugging rounds the first time). A store that uses ordinary Shopify
variants for size/color is simpler — see the earlier, variant-based
version of `check_stock.py` in the git history for that shape.

## One-time setup (you need to do this)

1. **Subscribe to notifications.** Install the ntfy app
   ([iOS](https://apps.apple.com/app/ntfy/id1625396347) /
   [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy))
   or open https://ntfy.sh/app in a browser, and subscribe to the topic:

   ```
   hoodie-restock-a1eb6a932d
   ```

   (Or just visit https://ntfy.sh/hoodie-restock-a1eb6a932d/ in a browser tab
   and leave it open — you'll see a browser notification too.) ntfy topics
   are public-by-name, so this one is a random string so nobody else stumbles
   onto it — don't share it anywhere public.

2. This branch is already the repo's default branch (the repo was empty
   before this was pushed), so the schedule is live as soon as it's on
   GitHub — nothing further to merge.

3. **(Optional) Run it once by hand** from the Actions tab →
   "Hoodie Stock Check" → "Run workflow" (tick "debug" for a verbose
   per-color/size log) to confirm it works. Check the run logs for the
   "Current status" line — it lists every color+size and whether it's in
   stock right now. As of this run, everything (all colors, all sizes)
   was sold out, so no notification is expected until that changes.

## Adjusting things later

- **Check frequency**: edit the cron expression in
  `.github/workflows/stock-check.yml` (`*/30 * * * *`, every 30 minutes).
  GitHub Actions doesn't reliably support intervals under ~5 minutes.
- **Daily status time**: edit the cron expression in
  `.github/workflows/health-check.yml` (`0 8 * * *` = 9am UK time while
  on BST). GitHub Actions cron is UTC-only and doesn't follow daylight
  saving, so this will drift to 8am UK time once the clocks change to
  GMT in late October — shift it back to `0 9 * * *` at that point if you
  want it to stay at 9am local.
- **Different product/store**: this scraping approach is specific to how
  this store's theme exposes colors and stock. A store using true Shopify
  variants for color would be simpler — see git history for the earlier,
  variant-based version of `check_stock.py`.
- **Notification channel**: swap the `notify()` function in
  `check_stock.py` for email/Discord/Slack if you'd rather not use ntfy.
