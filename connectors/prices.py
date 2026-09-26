"""Market price connector: €/m² by municipality (and district where known).

v1 loads data/market_prices.csv (asking prices from the Idealista and Fotocasa
monthly reports, with source and date on every row). Notary achieved prices
(Portal Estadístico del Notariado) can be added as rows with basis='notary';
scoring prefers notary rows when present.
"""
import csv
from pathlib import Path

CSV = Path(__file__).resolve().parent.parent / "data" / "market_prices.csv"


def load(path: Path = CSV) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["eur_m2"] = float(r["eur_m2"])
        r["area"] = r.get("area") or ""
    return rows


def lookup(rows: list[dict], municipality: str, area: str = "") -> dict | None:
    """Best price row: notary before asking, district before whole municipality."""
    m = (municipality or "").strip().lower()
    cands = [r for r in rows if r["municipality"].lower() == m]
    if not cands:
        return None
    a = (area or "").strip().lower()
    # keep the district row only if it matches; otherwise fall back to the municipality row
    cands = [r for r in cands if r["area"] == "" or (a and r["area"].lower() == a)]
    if not cands:
        return None
    def rank(r):
        return (r["basis"] != "notary", r["area"] == "")
    return sorted(cands, key=rank)[0]
