# Stock Agent

Watches the [Double Layer Polar Fleece Hoodie](https://unionkingdomclo.com/products/double-layer-polar-fleece-hoodie)
on unionkingdomclo.com and sends you a push notification the moment any
color comes back in stock.

## How it works

- `.github/workflows/stock-check.yml` runs on a GitHub Actions schedule
  (every 30 minutes) and can also be triggered manually.
- `check_stock.py` reads the store's Shopify product JSON endpoint
  (`/products/<handle>.json`), works out which colors currently have at
  least one available variant, and diffs that against `state.json` (the
  last known state, committed back to the repo after every run).
- Any color that flips from out-of-stock to in-stock triggers a push
  notification via [ntfy.sh](https://ntfy.sh) with a direct link to that
  variant.
- Colors are read dynamically from the product's options, so this keeps
  working even if the store adds/removes/renames colors.

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

2. **Merge this branch to your default branch.** GitHub only fires
   `schedule` triggers for workflow files that exist on the repo's default
   branch, so the 30-minute check won't actually start running until this
   is merged.

3. **(Optional) Run it once by hand** from the Actions tab →
   "Hoodie Stock Check" → "Run workflow", to confirm it works and to send
   yourself a test read of current stock (check the run logs for the
   "Current status" line — it lists every color and whether it's in stock
   right now).

## Adjusting things later

- **Check frequency**: edit the cron expression in
  `.github/workflows/stock-check.yml` (`*/30 * * * *`). GitHub Actions
  doesn't reliably support intervals under ~5 minutes.
- **Different product/store**: change `PRODUCT_URL` / `PRODUCT_PAGE` in
  `check_stock.py` (must be a Shopify store with the standard
  `/products/<handle>.json` endpoint).
- **Notification channel**: swap the `notify()` function in
  `check_stock.py` for email/Discord/Slack if you'd rather not use ntfy.
