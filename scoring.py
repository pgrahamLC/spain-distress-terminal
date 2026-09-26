"""Lot scoring: how far below achievable market value a lot is likely to clear."""

ASKING_HAIRCUT = 0.15   # asking €/m² -> achieved price; notary rows skip this
DEFAULT_RATIO = 62.0    # national median winning bid / valuation, % (SubastasIA)


def score_lot(lot: dict, price: dict | None, province_ratio: float | None) -> dict:
    flags = []
    valor = lot.get("valor_subasta") or lot.get("tasacion")
    m2 = lot.get("m2")
    ratio = province_ratio or DEFAULT_RATIO

    market = None
    if price and m2:
        per_m2 = price["eur_m2"] * (1 if price["basis"] == "notary" else 1 - ASKING_HAIRCUT)
        market = m2 * per_m2
    else:
        flags.append("no market value (missing m² or local price)")

    expected_clear = valor * ratio / 100 if valor else None
    valor_to_market = valor / market if valor and market else None
    discount = 1 - expected_clear / market if expected_clear and market else None

    if valor_to_market and valor_to_market > 1:
        flags.append("valuation above market: likely to go unsold or clear low")
    if (lot.get("procedure") or "").lower().startswith("voluntari"):
        flags.append("voluntary sale, not a forced seller")
    if lot.get("deposit") and valor and lot["deposit"] / valor > 0.1:
        flags.append("20% deposit: check surviving charges in the edict")
    if lot.get("year_built") and lot["year_built"] < 1970:
        flags.append(f"built {lot['year_built']}: budget for refurbishment")
    if valor and valor < 50000 and market and market > 2 * valor:
        flags.append("very low valuation vs market: verify occupancy and condition")

    score = None
    if discount is not None:
        score = max(0, min(100, round(discount * 125)))  # 80% discount -> 100
    return {
        "market_value": round(market) if market else None,
        "market_basis": price and f"{price['basis']} {price['eur_m2']:.0f} €/m² ({price['source']}, {price['as_of']})",
        "valor_to_market": round(valor_to_market, 3) if valor_to_market else None,
        "province_ratio": ratio,
        "expected_clear": round(expected_clear) if expected_clear else None,
        "expected_discount": round(discount, 3) if discount is not None else None,
        "score": score,
        "flags": flags,
    }
