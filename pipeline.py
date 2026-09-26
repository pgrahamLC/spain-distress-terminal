"""Daily pipeline: load lots, enrich from Catastro, pull insolvencies, score.

Run:  python pipeline.py            (today)
      python pipeline.py 2026-09-25 (a given bulletin date)
"""
import csv
import datetime as dt
import json
import sys
from pathlib import Path

import db
import scoring
from connectors import auctions, catastro, insolvency, prices

DATA = Path(__file__).parent / "data"


def load_province_stats() -> dict[str, dict]:
    with (DATA / "province_stats.csv").open(encoding="utf-8") as f:
        return {r["province"].lower(): r for r in csv.DictReader(f)}


def run(day: dt.date, online: bool = True) -> dict:
    con = db.connect()
    stats = load_province_stats()
    price_rows = prices.load()
    for p in price_rows:
        db.upsert(con, "market_prices", {k: p[k] for k in ("municipality", "area", "eur_m2", "basis", "source", "as_of")})
    for s in stats.values():
        db.upsert(con, "province_stats", {"province": s["province"], "closed": int(s["closed"]),
                  "active": int(s["active"]), "ratio_median": float(s["ratio_median"]),
                  "ratio_n": int(s["ratio_n"]), "median_bid": float(s["median_bid"])})

    lots = auctions.load_seed() + (auctions.load_feed() if online else [])
    scored, errors = [], []
    for lot in lots:
        area = lot.pop("area", "")
        if online and lot.get("catastro_ref") and (not lot.get("m2") or not lot.get("year_built")):
            try:
                info = catastro.lookup(lot["catastro_ref"])
                if info:
                    lot.setdefault("m2", info["m2"])
                    lot.setdefault("year_built", info["year_built"])
                    lot.setdefault("use", info["use"])
            except Exception as e:  # keep going; one bad lookup shouldn't stop the run
                errors.append(f"catastro {lot['boe_id']}: {e}")
        db.upsert(con, "lots", {k: v for k, v in lot.items() if k in LOT_COLS})
        st = stats.get((lot.get("province") or "").lower())
        result = scoring.score_lot(lot, prices.lookup(price_rows, lot.get("municipality"), area),
                                   float(st["ratio_median"]) if st else None)
        scored.append({**lot, "area": area, **result})

    ins = []
    if online:
        try:
            ins = insolvency.fetch(day)
            for row in ins:
                db.upsert(con, "insolvencies", row)
        except Exception as e:
            errors.append(f"insolvency {day}: {e}")
    con.commit()

    scored.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))
    out = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "bulletin_date": day.isoformat(),
           "lots": scored, "insolvencies_real_estate": [r for r in ins if r["is_real_estate"]],
           "insolvencies_total": len(ins), "errors": errors}
    (DATA / "latest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


LOT_COLS = {"boe_id", "municipality", "province", "address", "m2", "year_built", "use", "catastro_ref",
            "valor_subasta", "tasacion", "deposit", "procedure", "end_date", "source", "source_url"}

if __name__ == "__main__":
    day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date.today()
    offline = "--offline" in sys.argv
    res = run(day, online=not offline)
    print(f"{len(res['lots'])} lots scored, {res['insolvencies_total']} insolvency notices "
          f"({len(res['insolvencies_real_estate'])} real estate), {len(res['errors'])} errors")
    for e in res["errors"]:
        print("  !", e)
