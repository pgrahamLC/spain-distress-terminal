import datetime as dt
import json
from pathlib import Path

import pipeline
import scoring
from connectors import auctions, catastro, insolvency, prices

FIX = Path(__file__).parent / "fixtures"


def test_catastro_parse_reus():
    info = catastro.parse(json.loads((FIX / "catastro_reus.json").read_text()))
    assert info["m2"] == 63
    assert info["m2_with_common"] == 70
    assert info["year_built"] == 1960
    assert info["use"] == "Residencial"


def test_catastro_ref_validation():
    assert catastro.valid_ref("1074311CF4517C0009EH")
    assert not catastro.valid_ref("Finca 17972")


def test_insolvency_parse_flags_real_estate():
    boe = json.loads((FIX / "boe_sumario.json").read_text())
    rows = insolvency.parse_boe(boe, "2026-09-25")
    assert len(rows) == 2
    re_rows = [r for r in rows if r["is_real_estate"]]
    assert re_rows[0]["company"] == "PROMOCIONES LEVANTE SUR SL"
    borme = json.loads((FIX / "borme_sumario.json").read_text())
    rows = insolvency.parse_borme(borme, "2026-09-25")
    assert {r["act"] for r in rows} == {"disolución", "liquidación"}
    assert any(r["is_real_estate"] for r in rows)


def test_auction_clean_numbers():
    row = auctions.clean({"boe_id": "Lote SUB-JA-2026-265483", "valor_subasta": "83.761,17 €"})
    assert row["boe_id"] == "SUB-JA-2026-265483"
    assert row["valor_subasta"] == 83761.17
    assert auctions.clean({"boe_id": "no id"}) is None


def test_price_lookup_prefers_matching_district():
    rows = prices.load()
    assert prices.lookup(rows, "Madrid", "Usera")["eur_m2"] == 3626
    assert prices.lookup(rows, "Madrid", "Chamberí")["eur_m2"] == 6471   # no district row -> city
    assert prices.lookup(rows, "Nowhere") is None


def test_scoring_math():
    lot = {"valor_subasta": 100000, "m2": 100}
    price = {"eur_m2": 2000, "basis": "asking", "source": "x", "as_of": "2026-08"}
    s = scoring.score_lot(lot, price, 60)
    assert s["market_value"] == 170000               # 100 m2 x 2000 x 0.85
    assert s["expected_clear"] == 60000
    assert abs(s["expected_discount"] - (1 - 60000 / 170000)) < 1e-3


def test_scoring_flags_overvalued():
    s = scoring.score_lot({"valor_subasta": 200000, "m2": 50},
                          {"eur_m2": 2000, "basis": "asking", "source": "x", "as_of": "x"}, 70)
    assert any("above market" in f for f in s["flags"])


def test_pipeline_offline_runs_on_seed():
    out = pipeline.run(dt.date(2026, 9, 25), online=False)
    assert len(out["lots"]) >= 10
    scores = [r["score"] for r in out["lots"] if r["score"] is not None]
    assert scores == sorted(scores, reverse=True)
