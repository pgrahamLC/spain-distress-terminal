"""SQLite storage for the Spain Distress Terminal."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "spain_distress.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS lots (
    boe_id        TEXT PRIMARY KEY,   -- e.g. SUB-JA-2026-265483
    municipality  TEXT,
    province      TEXT,
    address       TEXT,
    m2            REAL,               -- built area (Catastro preferred)
    year_built    INTEGER,
    use           TEXT,
    catastro_ref  TEXT,
    valor_subasta REAL,
    tasacion      REAL,
    deposit       REAL,
    procedure     TEXT,               -- apremio / hipotecaria / voluntaria / AEAT
    end_date      TEXT,               -- ISO date
    source        TEXT,
    source_url    TEXT,
    updated_at    TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS market_prices (
    municipality TEXT,
    area         TEXT DEFAULT '',     -- district or zone, '' = whole municipality
    eur_m2       REAL,
    basis        TEXT,                -- asking / notary
    source       TEXT,
    as_of        TEXT,
    PRIMARY KEY (municipality, area, basis)
);
CREATE TABLE IF NOT EXISTS province_stats (
    province     TEXT PRIMARY KEY,
    closed       INTEGER,
    active       INTEGER,
    ratio_median REAL,                -- winning bid / tasación, %
    ratio_n      INTEGER,
    median_bid   REAL
);
CREATE TABLE IF NOT EXISTS insolvencies (
    id             TEXT PRIMARY KEY,  -- BOE/BORME item identifier
    pub_date       TEXT,
    company        TEXT,
    act            TEXT,              -- concurso / disolución / liquidación
    court_or_prov  TEXT,
    is_real_estate INTEGER,
    title          TEXT,
    url            TEXT
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def upsert(con: sqlite3.Connection, table: str, row: dict) -> None:
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    con.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({marks})", list(row.values()))
