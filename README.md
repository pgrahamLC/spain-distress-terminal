# Spain Distress Terminal (v1)

Finds Spanish residential lots likely to sell well below market: judicial and
tax auctions scored against local prices, plus a daily feed of real-estate
company insolvencies. Same stack as the AH Terminal: Python, FastAPI, SQLite,
GitHub Actions for the daily pull, Render for hosting.

## What each connector does

| Connector | Source | Status |
|---|---|---|
| `connectors/insolvency.py` | BOE daily summary (Juzgados de lo Mercantil: concurso declarations) and BORME Section C (dissolution, liquidation) | Built and tested on fixtures. Runs live from GitHub Actions or Render. |
| `connectors/catastro.py` | Catastro OVC web service: m², use, year built from a cadastral reference | Built, and checked live on two refs on 26 Sep 2026 |
| `connectors/prices.py` | €/m² by municipality and district (`data/market_prices.csv`) | Seeded with Idealista/Fotocasa Aug–Sep 2026 asking prices. Add notary rows (`basis=notary`) as you get them; they take priority. |
| `connectors/auctions.py` | Lots from `data/lots_seed.csv` (watchlist) and/or a licensed aggregator API | Seeded with 12 live lots closing 1–15 Oct 2026 |

The BOE auction portal itself (subastas.boe.es) disallows automated access in
its robots rules, so the connector does not scrape it. Feed it from a licensed
aggregator (set `AUCTION_FEED_URL` / `AUCTION_FEED_KEY` as repo secrets and
adjust `FIELD_MAP`) or add lots to the CSV by hand.

## How a lot is scored

1. Market value = m² × local €/m² × 0.85 (asking-to-achieved haircut; skipped for notary prices).
2. Expected clearing price = valor de subasta × the province's median winning bid / valuation (5-year SubastasIA data, `data/province_stats.csv`).
3. Score = expected discount to market × 125, capped 0–100.
4. Flags: valuation above market, voluntary sale, 20% deposit (check surviving charges), pre-1970 building, suspiciously low valuation.

## Run it

```bash
pip install -r requirements.txt
python -m pytest -q                 # 8 tests
python pipeline.py                  # live pull for today
python pipeline.py 2026-09-25 --offline   # score the seed lots only
uvicorn app:app --reload            # http://localhost:8000
```

API: `/api/lots?min_score=60`, `/api/insolvencies`, `/api/provinces`, `/api/status`.

## Deploy (free)

Everything runs on GitHub; no server needed.

1. Create a new GitHub repo and push this folder. A private repo needs a paid GitHub plan for Pages, so make it public or use a paid account.
2. Settings → Pages → Source: **GitHub Actions**.
3. Actions tab → **daily-pull** → Run workflow. It pulls data, commits `data/latest.json`, and publishes the page at `https://<your-user>.github.io/<repo>/`.
4. After that it runs itself 07:40 UTC Mon–Sat.

`app.py` and `render.yaml` are optional: use them only if you later want a live API (Render has a free tier that sleeps when idle).

## Next (v2)

- Registro Público Concursal (publicidadconcursal.es) for individuals and firms in insolvency.
- Servicer REO listings (Aliseda, Servihabitat, Haya, Altamira, Solvia) for time-on-market and price cuts.
- Notary achieved prices by postcode to replace the asking-price haircut.
