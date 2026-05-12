# BCV USD/VES Daily Rate — Serverless API

A zero-cost, zero-maintenance daily exchange rate feed for USD → Venezuelan
Bolívar, scraped from the [Banco Central de Venezuela](https://www.bcv.org.ve/)
and served as JSON over GitHub Pages.

## What you get

- `https://<username>.github.io/<repo>/rate.json` — latest rate
- `https://<username>.github.io/<repo>/history.json` — full history array
- `https://<username>.github.io/<repo>/` — small status page
- Updated automatically every day at **8 PM Venezuela time** (00:05 UTC)

CORS is open by default on GitHub Pages, so you can `fetch()` these from
any website with no proxy.

## One-time setup (≈ 5 minutes)

### 1. Create a new GitHub repo

Public repo (Pages on private repos requires a paid plan).

### 2. Push these files to it

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

### 3. Enable GitHub Pages

In the repo: **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: **main** / folder: **/docs**
- Save

Pages will give you the public URL — something like
`https://<username>.github.io/<repo>/`.

### 4. Allow Actions to commit back to the repo

**Settings → Actions → General → Workflow permissions**
- Select **Read and write permissions**
- Save

(Without this, the workflow can run but can't push the updated JSON.)

### 5. Trigger the first run manually

**Actions tab → "Update BCV USD/VES rate" → Run workflow**

After ~1 minute you'll see new commits adding `docs/rate.json` and
`docs/history.json`. After another ~1 minute the Pages site will serve them.

From then on, it runs automatically every day.

## Using the API from a website

```html
<script>
  fetch('https://<username>.github.io/<repo>/rate.json')
    .then(r => r.json())
    .then(d => {
      console.log(`1 USD = ${d.rate} VES`);
      console.log(`Date (VE): ${d.date_ve}`);
    });
</script>
```

Response shape:

```json
{
  "currency_pair": "USD/VES",
  "rate": "36.12345678",
  "date_ve": "2026-05-11",
  "fetched_at_utc": "2026-05-12T00:05:14+00:00",
  "source": "Banco Central de Venezuela",
  "source_url": "https://www.bcv.org.ve/"
}
```

`history.json` is an array sorted by `date_ve`:

```json
[
  { "date_ve": "2026-05-10", "rate": "36.0987",   "fetched_at_utc": "..." },
  { "date_ve": "2026-05-11", "rate": "36.12345678","fetched_at_utc": "..." }
]
```

## Schedule

GitHub Actions cron is **UTC only**. Venezuela is fixed UTC-4 (no DST):

| Venezuela local | UTC cron       |
| --------------- | -------------- |
| 8:00 PM         | `0 0 * * *`    |
| **8:05 PM**     | **`5 0 * * *`** ← used here |

The extra 5 minutes reduces jitter — GitHub queues scheduled jobs and busy
times can delay them by 5-15 minutes.

## Caveats

- **Not an official BCV API.** It scrapes their homepage. If they redesign,
  the `<div id="dolar">` selector might break — the workflow will fail and
  you'll get an email from GitHub.
- **No SLA.** Best effort. Don't use for anything where a stale rate causes
  financial harm.
- **BCV doesn't publish on weekends/holidays.** Those days the script either
  picks up the previous business day's rate (the dedupe check skips the
  duplicate) or fails gracefully.
- **The repo grows over time.** `history.json` will be a few KB per year.
  Not a concern.

## Running locally to test

```bash
pip install -r requirements.txt
python update_rate.py
cat docs/rate.json
```
