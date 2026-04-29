"""
forecast_fetcher.py — OpenMeteo ensemble fetch (free tier).

Returns ensemble member temperatures for a city + date range.
Used by prob_calculator to compute threshold probabilities.

Verified V1 (2026-04-29): 143 members across 4 models.
- gfs025 (NCEP GEFS): 31 members
- ecmwf_ifs025: 51 members
- icon_seamless: 40 members
- gem_global: 21 members
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
MODELS = ["gfs025", "ecmwf_ifs025", "icon_seamless", "gem_global"]
TIMEOUT_SEC = 15
MAX_RETRY = 3


@dataclass
class CityForecast:
    """Hourly ensemble forecast for one city."""

    city: str
    lat: float
    lon: float
    hours_utc: list[str]               # ISO8601 hourly timestamps, UTC
    members: dict[str, list[list[float]]]
    # members[model_name] = [member1_hourly_temps_C, member2_hourly_temps_C, ...]

    def all_members_flat(self) -> list[list[float]]:
        """Concatenate all 143 members across the 4 models."""
        out: list[list[float]] = []
        for model_members in self.members.values():
            out.extend(model_members)
        return out

    def total_members(self) -> int:
        return sum(len(m) for m in self.members.values())


def _parse_members(payload: dict, model_short: str) -> list[list[float]]:
    """Extract per-member hourly temperatures.

    OpenMeteo ensemble returns keys like:
        temperature_2m_ncep_gefs_seamless           (deterministic / control)
        temperature_2m_member01_ncep_gefs_seamless  (perturbed members)

    We treat the deterministic run as member 0 and include it.
    """
    hourly = payload.get("hourly", {})
    matched: list[tuple[int, list[float]]] = []
    for k, v in hourly.items():
        if not k.startswith("temperature_2m"):
            continue
        if "member" in k:
            # member01 .. memberNN
            try:
                idx = int(k.split("member")[1][:2])
            except ValueError:
                idx = -1
        elif k == f"temperature_2m" or k.startswith("temperature_2m_"):
            idx = 0
        else:
            continue
        if v is None:
            continue
        # Filter Nones inside the series
        clean = [float(x) for x in v if x is not None]
        if clean:
            matched.append((idx, clean))
    matched.sort(key=lambda t: t[0])
    return [series for _, series in matched]


def fetch_city_forecast(
    city: str,
    lat: float,
    lon: float,
    forecast_days: int = 3,
    models: Optional[list[str]] = None,
) -> CityForecast:
    """Fetch ensemble for one city across all 4 models.

    Each model is fetched separately because OpenMeteo's combined-models
    endpoint coalesces members under one prefix and we lose the model breakdown.
    """
    use_models = models or MODELS
    members_by_model: dict[str, list[list[float]]] = {}
    hours_ref: list[str] = []

    for model in use_models:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m",
            "models": model,
            "forecast_days": forecast_days,
            "timezone": "UTC",
        }
        for attempt in range(MAX_RETRY):
            try:
                r = requests.get(ENSEMBLE_URL, params=params, timeout=TIMEOUT_SEC)
                r.raise_for_status()
                data = r.json()
                break
            except (requests.RequestException, ValueError) as exc:
                if attempt == MAX_RETRY - 1:
                    # Patch P17: API redundancy — log and skip this model, don't crash.
                    print(f"[forecast_fetcher] {model} failed after {MAX_RETRY}: {exc}")
                    data = {}
                    break
                time.sleep(2 ** attempt)
        if not data:
            members_by_model[model] = []
            continue
        if not hours_ref:
            hours_ref = data.get("hourly", {}).get("time", []) or []
        members_by_model[model] = _parse_members(data, model)

    return CityForecast(
        city=city,
        lat=lat,
        lon=lon,
        hours_utc=hours_ref,
        members=members_by_model,
    )


# --- City registry ---------------------------------------------------------
# Map of cities Polymarket runs weather markets for.
# Coordinates use the airport observation point when known (Patch P6: settlement source).
# When the airport coord is uncertain, the city center is used and a note is left.
CITIES: dict[str, tuple[float, float]] = {
    # (lat, lon) — airport coordinates when we know the resolution source
    "New York City": (40.7794, -73.8803),  # KLGA LaGuardia
    "Atlanta": (33.6407, -84.4277),         # KATL
    "Toronto": (43.6777, -79.6248),         # CYYZ
    "Miami": (25.7959, -80.2870),           # KMIA
    "Sao Paulo": (-23.6273, -46.6566),      # SBSP Congonhas
    "Seattle": (47.4502, -122.3088),        # KSEA
    "Austin": (30.1975, -97.6664),          # KAUS
    "Los Angeles": (33.9416, -118.4085),    # KLAX
    "Tokyo": (35.5494, 139.7798),           # RJTT Haneda
    "Seoul": (37.4602, 126.4407),           # RKSI Incheon
    "London": (51.4700, -0.4543),           # EGLL Heathrow
    "Hong Kong": (22.3080, 113.9185),       # VHHH
}


if __name__ == "__main__":
    # Smoke test: fetch NYC forecast and print member count + first hour.
    fc = fetch_city_forecast("New York City", *CITIES["New York City"])
    print(f"city={fc.city} hours={len(fc.hours_utc)} total_members={fc.total_members()}")
    for model, members in fc.members.items():
        print(f"  {model}: {len(members)} members")
    if fc.hours_utc and fc.members:
        # First hour temp distribution across all members
        first_hour = [m[0] for m_list in fc.members.values() for m in m_list if m]
        if first_hour:
            print(f"  hour[0]={fc.hours_utc[0]}  min={min(first_hour):.1f}  "
                  f"max={max(first_hour):.1f}  mean={sum(first_hour)/len(first_hour):.1f}°C")
