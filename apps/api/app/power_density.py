"""How many MW of solar or wind a square kilometre of buildable land yields.

This one constant sets every candidate's assumed capacity, and through it every
capex and every NPV in the platform. It used to be a literature range -- openly
flagged as not Greece-specific and not re-verified, but still the most leveraged
guess in the chain.

`pipeline/calibrate_power_density.py` replaces the guess with a measurement:
the footprints of Greece's own built solar and wind plants, from OpenStreetMap,
divided into their tagged capacities. This module reads that measurement and
decides, per carrier, whether it is strong enough to use.

The decision is deliberately conservative. A measured median is used only when
it rests on at least `MIN_SAMPLE_PLANTS` plants; below that the literature value
stands, because a density derived from two or three plants is a worse guess than
a published range, not a better one. Either way the basis travels with the
number into the API response, so a reader can always tell which they are looking
at.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# The pre-existing external literature range, kept as the fallback. Solar:
# commonly-cited utility-PV figures around 30-45 MW/km^2. Onshore wind:
# commonly-cited array-density figures around 5-8 MW/km^2, set by turbine
# spacing rather than turbine footprint.
LITERATURE_MW_PER_KM2 = {"solar": 40.0, "wind": 6.0}

# Below this many measured plants, the measurement is noise and the literature
# value is the better estimate.
MIN_SAMPLE_PLANTS = 8

MEASUREMENT_FILENAME = "power_density_greece.json"

BASIS_MEASURED = "measured_greek_fleet"
BASIS_LITERATURE = "literature_range"


@dataclass(frozen=True)
class PowerDensity:
    carrier: str
    mw_per_km2: float
    basis: str
    plant_count: int | None = None
    statistic: str | None = None
    total_area_km2: float | None = None
    measured_at_utc: str | None = None

    def describe(self) -> str:
        if self.basis == BASIS_MEASURED:
            over = f" covering {self.total_area_km2:,.0f} km^2" if self.total_area_km2 else ""
            how = (
                "the median of their footprints"
                if self.statistic == "median"
                else "their combined capacity over their combined area"
            )
            return (
                f"{self.mw_per_km2:.1f} MW/km^2, measured from {self.plant_count} built Greek "
                f"{self.carrier} plants{over} -- {how}"
            )
        return (
            f"{self.mw_per_km2:.0f} MW/km^2, an external literature figure -- not Greece-specific "
            "(too few built plants carry both a mapped footprint and a capacity to measure one)"
        )


def measurement_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "generated" / MEASUREMENT_FILENAME


@lru_cache(maxsize=1)
def load_measurement() -> dict | None:
    path = measurement_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@lru_cache(maxsize=8)
def get_power_density(carrier: str) -> PowerDensity | None:
    """The density to use for this carrier, with the basis it rests on. None
    for a carrier this platform does not size (anything but solar and wind)."""
    literature = LITERATURE_MW_PER_KM2.get(carrier)
    measurement = load_measurement()
    stats = ((measurement or {}).get("carriers") or {}).get(carrier) or {}
    count = stats.get("plant_count") or 0
    headline = stats.get("headline_mw_per_km2")

    if headline and count >= MIN_SAMPLE_PLANTS:
        return PowerDensity(
            carrier=carrier,
            mw_per_km2=float(headline),
            basis=BASIS_MEASURED,
            plant_count=int(count),
            statistic=stats.get("headline_statistic"),
            total_area_km2=stats.get("total_area_km2"),
            measured_at_utc=(measurement or {}).get("measured_at_utc"),
        )

    if literature is None:
        return None
    return PowerDensity(
        carrier=carrier,
        mw_per_km2=literature,
        basis=BASIS_LITERATURE,
        plant_count=int(count) or None,
    )


def mw_per_km2(carrier: str) -> float | None:
    density = get_power_density(carrier)
    return density.mw_per_km2 if density else None
