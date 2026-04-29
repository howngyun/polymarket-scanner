"""
market_scanner.py — fetch and parse Polymarket weather markets.

Filters per Patch P10 (temperature range markets only) and P25 (1~3 day horizon).
Returns structured `WeatherMarket` rows ready for prob_calculator.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

GAMMA_URL = "https://gamma-api.polymarket.com/markets"
TIMEOUT_SEC = 15

# Patterns we accept (P10 — temperature only for v1)
# Examples:
#   "Will the highest temperature in Los Angeles be 53°F or below on May 1?"
#   "Will the highest temperature in Helsinki be 11°C on April 29?"
#   "Will the highest temperature in Atlanta be between 68-69°F on April 30?"
#   "Will the lowest temperature in Tokyo be 14°C on April 29?"
QUESTION_RE = re.compile(
    r"Will the (?P<agg>highest|lowest) temperature in (?P<city>.+?) be "
    r"(?:between (?P<lo>-?\d+)-(?P<hi>-?\d+)|(?P<thr>-?\d+))"
    r"\s*°(?P<unit>[FC])"
    r"(?:\s*(?P<dir>or below|or higher))?"
    r" on (?P<date>.+?)\?$",
    re.IGNORECASE,
)


@dataclass
class WeatherMarket:
    """One parsed Polymarket weather market."""

    market_id: str            # condition_id
    question: str
    slug: str
    city: str
    agg: str                  # 'high' or 'low' — daily max or min
    op: str                   # 'exact' | 'le' | 'ge' | 'range'
    threshold_c: float        # threshold (in Celsius, normalized)
    threshold_hi_c: Optional[float]  # for range markets only
    original_unit: str        # 'F' or 'C' — needed downstream for correct bin width (BUG B1)
    end_date: datetime        # resolution timestamp UTC
    yes_token_id: str
    no_token_id: str
    yes_price: float          # current outcomePrices for Yes (mid/last quote)
    no_price: float
    best_ask_yes: Optional[float]   # actual ask we'd pay buying YES
    best_bid_yes: Optional[float]   # actual bid we'd hit selling YES (= 1 - askNO mostly)
    volume_24h: float
    liquidity: float
    resolution_source: str    # short tag e.g. "Wunderground/LAX" — used for P6 whitelist

    def days_to_resolution(self, now: Optional[datetime] = None) -> float:
        n = now or datetime.now(timezone.utc)
        return (self.end_date - n).total_seconds() / 86400.0


def _f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def _parse_question(q: str) -> Optional[dict]:
    """Parse the question text into structured fields. Returns None if it
    doesn't match the supported patterns (e.g., snowfall, hurricane)."""
    m = QUESTION_RE.match(q.strip())
    if not m:
        return None
    g = m.groupdict()
    unit = g["unit"].upper()
    is_f = unit == "F"
    convert = _f_to_c if is_f else (lambda x: float(x))

    if g["lo"] is not None and g["hi"] is not None:
        op = "range"
        lo = convert(float(g["lo"]))
        hi = convert(float(g["hi"]))
        thr_c = lo
        thr_hi_c = hi
    else:
        thr = float(g["thr"])
        thr_c = convert(thr)
        thr_hi_c = None
        if g["dir"]:
            d = g["dir"].lower()
            op = "le" if "below" in d else "ge"
        else:
            op = "exact"

    return {
        "city": g["city"].strip(),
        "agg": "high" if g["agg"].lower() == "highest" else "low",
        "op": op,
        "threshold_c": thr_c,
        "threshold_hi_c": thr_hi_c,
        "unit": unit,  # original unit (kept for description)
    }


def _extract_resolution_source(desc: str) -> str:
    """Pull a short tag from the market description for the P6 whitelist.

    We need station-level identification because the same city can have
    multiple official stations and a 1°F mismatch ruins the bet.
    """
    if not desc:
        return ""
    src = ""
    if "wunderground" in desc.lower():
        src = "wunderground"
    # Match e.g. "Madrid-Barajas Airport Station" — require the prior word to
    # not be "the" / "this" / a sentence boundary so we don't grab phrases like
    # "this market will resolve... Airport Station".
    m = re.search(
        r"\b(?!the |this |a |that |an )"
        r"([A-Z][A-Za-z'-]+(?:[ -][A-Z][A-Za-z'-]+){0,3} (?:International )?(?:Airport|Station)(?: Station)?)",
        desc,
    )
    if m:
        src = (src + "/" + m.group(1)) if src else m.group(1)
    return src[:80]


# Cities our forecast_fetcher knows how to fetch.
# (Other cities still parse, but prob_calculator will skip them until we add coords.)
from weatherbot.forecast_fetcher import CITIES as KNOWN_CITIES


def fetch_active_weather_markets(
    *,
    min_days: float = 0.0,
    max_days: float = 3.0,            # P25 — 1~3 day horizon (we accept 0~3)
    min_liquidity: float = 100.0,     # P5 — depth check (refined later in edge_filter)
    only_known_cities: bool = True,
    limit_per_page: int = 500,
    max_pages: int = 4,
) -> list[WeatherMarket]:
    """Fetch + filter weather markets.

    Patch references:
      P10 — only temperature markets (regex enforces this)
      P25 — only 0~3 day horizon
      P5  — preliminary liquidity floor
      P6  — resolution source captured for whitelist (caller decides)
    """
    out: list[WeatherMarket] = []
    now = datetime.now(timezone.utc)

    for page in range(max_pages):
        params = {
            "closed": "false",
            "limit": limit_per_page,
            "offset": page * limit_per_page,
            "order": "volume",
            "ascending": "false",
        }
        try:
            r = requests.get(GAMMA_URL, params=params, timeout=TIMEOUT_SEC)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as exc:
            print(f"[market_scanner] page {page} failed: {exc}")
            break

        if not data:
            break

        for m in data:
            q = m.get("question", "") or ""
            parsed = _parse_question(q)
            if not parsed:
                continue
            if only_known_cities and parsed["city"] not in KNOWN_CITIES:
                continue

            # Resolution date — normalize to UTC-aware
            end_iso = m.get("endDateIso") or m.get("endDate")
            if not end_iso:
                continue
            try:
                end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            days_left = (end_dt - now).total_seconds() / 86400.0
            if days_left < min_days or days_left > max_days:
                continue

            liquidity = float(m.get("liquidityNum") or 0.0)
            if liquidity < min_liquidity:
                continue

            # Outcomes / tokens
            outcomes = m.get("outcomes")
            prices = m.get("outcomePrices")
            tokens = m.get("clobTokenIds")
            if isinstance(outcomes, str):
                import json as _j
                outcomes = _j.loads(outcomes)
                prices = _j.loads(prices) if isinstance(prices, str) else prices
                tokens = _j.loads(tokens) if isinstance(tokens, str) else tokens
            if not (outcomes and prices and tokens) or len(outcomes) != 2:
                continue
            try:
                yes_idx = outcomes.index("Yes")
                no_idx = 1 - yes_idx
            except ValueError:
                continue

            try:
                yes_price = float(prices[yes_idx])
                no_price = float(prices[no_idx])
            except (TypeError, ValueError):
                continue

            wm = WeatherMarket(
                market_id=m.get("conditionId", "") or "",
                question=q,
                slug=m.get("slug", "") or "",
                city=parsed["city"],
                agg=parsed["agg"],
                op=parsed["op"],
                threshold_c=parsed["threshold_c"],
                threshold_hi_c=parsed["threshold_hi_c"],
                original_unit=parsed["unit"],
                end_date=end_dt,
                yes_token_id=str(tokens[yes_idx]),
                no_token_id=str(tokens[no_idx]),
                yes_price=yes_price,
                no_price=no_price,
                best_ask_yes=(float(m["bestAsk"]) if m.get("bestAsk") is not None else None),
                best_bid_yes=(float(m["bestBid"]) if m.get("bestBid") is not None else None),
                volume_24h=float(m.get("volume24hr") or 0.0),
                liquidity=liquidity,
                resolution_source=_extract_resolution_source(m.get("description", "") or ""),
            )
            out.append(wm)

    return out


if __name__ == "__main__":
    markets = fetch_active_weather_markets(only_known_cities=False)
    print(f"weather markets returned: {len(markets)}")
    by_city: dict[str, int] = {}
    by_op: dict[str, int] = {}
    for m in markets[:30]:
        days = m.days_to_resolution()
        print(
            f"  [{m.liquidity:>7,.0f}] {m.city:>15s} | {m.agg:>4s} {m.op:>5s} "
            f"thr={m.threshold_c:>5.1f}°C  d={days:>4.1f}  "
            f"yes={m.yes_price:.3f}  src='{m.resolution_source}'"
        )
        by_city[m.city] = by_city.get(m.city, 0) + 1
        by_op[m.op] = by_op.get(m.op, 0) + 1
    print(f"\nsummary: {len(markets)} markets")
    print(f"  by op: {by_op}")
    print(f"  by city (top 8): {dict(sorted(by_city.items(), key=lambda x:-x[1])[:8])}")
