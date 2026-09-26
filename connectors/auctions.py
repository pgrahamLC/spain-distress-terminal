"""Auction lot connector.

The BOE auction portal (subastas.boe.es) disallows automated access in its
robots rules, so this connector does NOT scrape it. Lots come in from:

1. data/lots_seed.csv       - a watchlist you edit by hand (or export from an
                               aggregator you licence), one row per lot.
2. A licensed aggregator API - set AUCTION_FEED_URL and AUCTION_FEED_KEY; the
                               response is mapped with FIELD_MAP below.

Either way each lot is keyed by its BOE ID (SUB-XX-YYYY-NNNNNN).
"""
import csv
import os
import re
from pathlib import Path
import httpx

from . import USER_AGENT

SEED = Path(__file__).resolve().parent.parent / "data" / "lots_seed.csv"
BOE_ID = re.compile(r"SUB-[A-Z]{2}-\d{4}-\d{5,7}")

# Map aggregator JSON field names onto ours; adjust to the vendor you pick.
FIELD_MAP = {
    "boe_id": "id", "municipality": "municipio", "province": "provincia",
    "address": "direccion", "valor_subasta": "valor_subasta", "tasacion": "tasacion",
    "deposit": "deposito", "end_date": "fecha_fin", "procedure": "tipo",
    "catastro_ref": "referencia_catastral", "source_url": "url",
}
NUMERIC = {"valor_subasta", "tasacion", "deposit", "m2"}


def _num(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("€", "").replace(" ", "")
    if "," in s and "." in s:          # 1.234,56 -> 1234.56
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def clean(row: dict) -> dict | None:
    boe = BOE_ID.search(str(row.get("boe_id", "")))
    if not boe:
        return None
    out = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if v not in ("", None)}
    out["boe_id"] = boe.group(0)
    for k in NUMERIC & out.keys():
        out[k] = _num(out[k])
    if "year_built" in out:
        y = _num(out["year_built"])
        out["year_built"] = int(y) if y else None
    return out


def load_seed(path: Path = SEED) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [r for r in (clean(row) for row in csv.DictReader(f)) if r]


def load_feed() -> list[dict]:
    url, key = os.getenv("AUCTION_FEED_URL"), os.getenv("AUCTION_FEED_KEY")
    if not url:
        return []
    r = httpx.get(url, headers={"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    rows = [{ours: it.get(theirs) for ours, theirs in FIELD_MAP.items()} for it in items]
    return [r for r in (clean(x) for x in rows) if r]
