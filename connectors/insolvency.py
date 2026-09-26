"""Insolvency connector: BOE + BORME open-data daily summaries.

- BOE sumario, Sección IV (Juzgados de lo Mercantil): concurso declarations.
- BORME sumario, Sección C: disolución / liquidación notices per company.

The API needs an `Accept: application/json` header (plain browser-style
fetches return HTTP 400). Items are flagged as real estate by name keywords.
"""
import datetime as dt
import re
import httpx

from . import USER_AGENT

BOE_SUMARIO = "https://www.boe.es/datosabiertos/api/boe/sumario/{d}"
BORME_SUMARIO = "https://www.boe.es/datosabiertos/api/borme/sumario/{d}"

RE_KEYWORDS = re.compile(
    r"inmobiliari|promoci|promotor|construcci|constructor|patrimoni|residencial|"
    r"vivienda|edificaci|urbaniz|desarrollos|real estate|homes|properties|inversiones",
    re.I)
ACT_KEYWORDS = [
    ("concurso", re.compile(r"concurs", re.I)),
    ("liquidación", re.compile(r"liquidaci", re.I)),
    ("disolución", re.compile(r"disoluci", re.I)),
    ("extinción", re.compile(r"extinci", re.I)),
]


def _walk(node, path=()):
    """Yield (item, path_names) for every dict that looks like a sumario item."""
    if isinstance(node, dict):
        names = path + tuple(str(node[k]) for k in ("nombre", "codigo") if k in node)
        if "identificador" in node and "titulo" in node:
            yield node, names
        for v in node.values():
            yield from _walk(v, names)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v, path)


def _url(item: dict) -> str | None:
    for key in ("url_html", "url_pdf", "url_xml"):
        v = item.get(key)
        if isinstance(v, dict):
            v = v.get("texto") or v.get("url")
        if v:
            return v
    return None


def classify(title: str, context: str) -> str | None:
    text = f"{context} {title}"
    for name, rx in ACT_KEYWORDS:
        if rx.search(text):
            return name
    return None


def parse_boe(payload: dict, pub_date: str) -> list[dict]:
    out = []
    for item, path in _walk(payload):
        ctx = " / ".join(path)
        if "mercantil" not in ctx.lower():
            continue
        title = item.get("titulo", "")
        act = classify(title, ctx) or "concurso"
        out.append({
            "id": item["identificador"], "pub_date": pub_date,
            "company": _company_from_title(title), "act": act,
            "court_or_prov": path[-1] if path else "",
            "is_real_estate": int(bool(RE_KEYWORDS.search(title))),
            "title": title, "url": _url(item),
        })
    return out


def parse_borme(payload: dict, pub_date: str) -> list[dict]:
    out = []
    for item, path in _walk(payload):
        ctx = " / ".join(path)
        title = item.get("titulo", "")
        act = classify(title, ctx)
        if not act:
            continue
        out.append({
            "id": item["identificador"], "pub_date": pub_date,
            "company": _company_from_title(title), "act": act,
            "court_or_prov": path[-1] if path else "",
            "is_real_estate": int(bool(RE_KEYWORDS.search(title))),
            "title": title, "url": _url(item),
        })
    return out


def _company_from_title(title: str) -> str:
    m = re.search(r"([A-ZÁÉÍÓÚÑ0-9][A-ZÁÉÍÓÚÑ0-9 .,&'-]+?(?:S\.?L\.?U?|S\.?A\.?U?|SOCIEDAD LIMITADA|SOCIEDAD ANÓNIMA))\b",
                  title)
    return (m.group(1) if m else title).strip(" .,")


def fetch(day: dt.date, client: httpx.Client | None = None) -> list[dict]:
    own = client is None
    client = client or httpx.Client(
        timeout=30, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    d = day.strftime("%Y%m%d")
    rows: list[dict] = []
    try:
        for url, parser in ((BOE_SUMARIO, parse_boe), (BORME_SUMARIO, parse_borme)):
            r = client.get(url.format(d=d))
            if r.status_code == 404:  # no bulletin that day (Sundays, holidays)
                continue
            r.raise_for_status()
            rows += parser(r.json(), day.isoformat())
    finally:
        if own:
            client.close()
    return rows
