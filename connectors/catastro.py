"""Catastro connector: built area, use and year built from a cadastral reference.

Uses the free OVC web service (no key). Verified 26 Sep 2026 against
1074311CF4517C0009EH (Reus, 63 m² + 7 m² common, 1960).
"""
import re
import httpx

from . import USER_AGENT

URL = ("https://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/"
       "COVCCallejero.svc/json/Consulta_DNPRC")
RC_PATTERN = re.compile(r"^[0-9A-Z]{14}([0-9A-Z]{6})?$")


def valid_ref(ref: str | None) -> bool:
    return bool(ref) and bool(RC_PATTERN.match(ref.replace(" ", "").upper()))


def parse(payload: dict) -> dict | None:
    """Pull m², use and year from a Consulta_DNPRC JSON response."""
    res = payload.get("consulta_dnprcResult") or payload
    bico = res.get("bico")
    if not bico:
        return None  # multiple units or not found; caller can list them
    bi = bico.get("bi", {})
    debi = bi.get("debi", {})
    private_m2 = None
    common_m2 = 0.0
    for c in bico.get("lcons", []) or []:
        m2 = float((c.get("dfcons") or {}).get("stl", 0) or 0)
        label = (c.get("lcd") or "").upper()
        if "ELEMENTOS COMUNES" in label:
            common_m2 += m2
        elif private_m2 is None:
            private_m2 = m2
    if private_m2 is None and debi.get("sfc"):
        private_m2 = float(debi["sfc"])
    year = debi.get("ant")
    return {
        "m2": private_m2,
        "m2_with_common": (private_m2 or 0) + common_m2 if private_m2 else None,
        "use": debi.get("luso"),
        "year_built": int(year) if year and str(year).isdigit() else None,
        "address": bi.get("ldt"),
    }


def lookup(ref: str, client: httpx.Client | None = None) -> dict | None:
    if not valid_ref(ref):
        return None
    own = client is None
    client = client or httpx.Client(timeout=20, headers={"User-Agent": USER_AGENT})
    try:
        r = client.get(URL, params={"RefCat": ref.replace(" ", "").upper()})
        r.raise_for_status()
        return parse(r.json())
    finally:
        if own:
            client.close()
