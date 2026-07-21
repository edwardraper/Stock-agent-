# Stock Agent

Watches the [Double Layer Polar Fleece Hoodie](https://unionkingdomclo.com/products/double-layer-polar-fleece-hoodie)
on unionkingdomclo.com, in every color, and sends you a push notification
the moment any color/size comes back in stock.

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

`.github/workflows/stock-check.yml` runs this on a GitHub Actions
schedule (every 30 minutes) and can also be triggered manually.

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
  `.github/workflows/stock-check.yml` (`*/30 * * * *`). GitHub Actions
  doesn't reliably support intervals under ~5 minutes.
- **Different product/store**: this scraping approach is specific to how
  this store's theme exposes colors and stock. A store using true Shopify
  variants for color would be simpler — see git history for the earlier,
  variant-based version of `check_stock.py`.
- **Notification channel**: swap the `notify()` function in
  `check_stock.py` for email/Discord/Slack if you'd rather not use ntfy.
