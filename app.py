"""FastAPI app: JSON API plus the single-page terminal."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

import db

ROOT = Path(__file__).parent
app = FastAPI(title="Spain Distress Terminal")


def _latest() -> dict:
    p = ROOT / "data" / "latest.json"
    if not p.exists():
        raise HTTPException(503, "No pipeline run yet. Run: python pipeline.py")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/api/lots")
def lots(min_score: int = 0, province: str | None = None):
    rows = _latest()["lots"]
    return [r for r in rows if (r.get("score") or 0) >= min_score
            and (not province or (r.get("province") or "").lower() == province.lower())]


@app.get("/api/insolvencies")
def insolvencies(real_estate_only: bool = True, limit: int = 200):
    con = db.connect()
    q = "SELECT * FROM insolvencies" + (" WHERE is_real_estate=1" if real_estate_only else "")
    return [dict(r) for r in con.execute(q + " ORDER BY pub_date DESC LIMIT ?", (limit,))]


@app.get("/api/provinces")
def provinces():
    con = db.connect()
    return [dict(r) for r in con.execute("SELECT * FROM province_stats ORDER BY ratio_median")]


@app.get("/api/status")
def status():
    d = _latest()
    return {"generated": d["generated"], "lots": len(d["lots"]),
            "insolvencies_total": d["insolvencies_total"], "errors": d["errors"]}


@app.get("/")
def index():
    return FileResponse(ROOT / "webapp" / "index.html")
