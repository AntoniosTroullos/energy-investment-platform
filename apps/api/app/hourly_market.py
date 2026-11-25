"""The hourly market layer of a solved scenario, as plain data.

`pipeline/extract_hourly_market.py` runs on the solver side of the bridge,
reads a solved `network.nc` and writes one compact JSON per case into
`data/generated/hourly_market/`. This module is the read side: stdlib + pydantic
only, no pandas, no pypsa, so the API keeps its small deployable footprint and a
deployment with no solver behind it still serves real hourly-derived economics.

What it adds over `ScenarioMetrics`
-----------------------------------
`average_marginal_price_by_bus` is an average over hours. A technology is not
paid the average hour -- it is paid the hours it produces. For solar those are
the same hours solar floods the market, so its captured price sits well below
the average and the gap widens as more solar is built. That gap (the capture
rate) is the single most important number in a renewable investment case and no
annual average can express it.

Three figures per region and carrier:

  realised capture price     what the solved fleet was actually paid, after any
                             curtailment the solver imposed on it
  availability capture price what a NEW price-taking plant at that location
                             would be paid, weighted by what the technology can
                             produce rather than by what the existing fleet was
                             allowed to produce. This is the candidate-economics
                             input -- a new project is not bound by the curtailment
                             history of the fleet already there.
  capture rate               availability capture / the region's time-weighted
                             average price. Under 100 % is cannibalisation.

Every figure is weighted by the solve's own snapshot weightings, so a 12
representative-day solve scaled to 8,760 h is summarised the way the solver
itself valued it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

HOURLY_MARKET_DIRNAME = "hourly_market"


class CarrierMarketPosition(BaseModel):
    """One technology's market position at one location."""

    model_config = ConfigDict(extra="allow")

    installed_capacity_mw: float | None = None
    generation_mwh: float | None = None
    realised_capacity_factor_pct: float | None = None
    realised_capture_price_eur_per_mwh: float | None = None
    # Variable (weather-driven) carriers only -- a dispatchable plant's
    # "availability" is a decision, not a physical profile, so these stay None.
    availability_capacity_factor_pct: float | None = None
    availability_capture_price_eur_per_mwh: float | None = None
    curtailment_pct: float | None = None
    capture_rate_pct: float | None = None


class RegionMarketPosition(BaseModel):
    model_config = ConfigDict(extra="allow")

    time_weighted_price_eur_per_mwh: float | None = None
    load_weighted_price_eur_per_mwh: float | None = None
    load_mwh: float | None = None
    peak_load_mw: float | None = None
    carriers: dict[str, CarrierMarketPosition] = Field(default_factory=dict)


class PriceDuration(BaseModel):
    model_config = ConfigDict(extra="allow")

    p5: float | None = None
    p25: float | None = None
    p50: float | None = None
    p75: float | None = None
    p95: float | None = None


class NationalMarketPosition(BaseModel):
    model_config = ConfigDict(extra="allow")

    time_weighted_price_eur_per_mwh: float | None = None
    load_weighted_price_eur_per_mwh: float | None = None
    total_load_mwh: float | None = None
    peak_load_mw: float | None = None
    price_duration_eur_per_mwh: PriceDuration = Field(default_factory=PriceDuration)
    near_zero_price_hours: float | None = None
    carriers: dict[str, CarrierMarketPosition] = Field(default_factory=dict)


class Corridor(BaseModel):
    # `from` is a Python keyword, so the field is `from_bus` and the alias
    # carries the extractor's own spelling in both directions.
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    line: str
    from_bus: str = Field(alias="from")
    to_bus: str = Field(alias="to")
    rating_mw: float | None = None
    mean_utilisation_pct: float | None = None
    peak_utilisation_pct: float | None = None
    congested_hours: float | None = None


class NetworkStress(BaseModel):
    model_config = ConfigDict(extra="allow")

    mean_region_price_spread_eur_per_mwh: float | None = None
    max_region_price_spread_eur_per_mwh: float | None = None
    line_count: int | None = None
    mean_utilisation_pct: float | None = None
    congested_corridor_hours: float | None = None
    total_transfer_capacity_mw: float | None = None
    share_of_hours_with_a_congested_corridor_pct: float | None = None
    corridors: list[Corridor] = Field(default_factory=list)


class MarketSeries(BaseModel):
    """The hourly series behind the charts. Present only for cases extracted
    with series enabled -- a long chronological case omits them so the file
    stays small, and every consumer must handle their absence."""

    model_config = ConfigDict(extra="allow")

    timestamps: list[str] = Field(default_factory=list)
    weights_hours: list[float] = Field(default_factory=list)
    national_price_eur_per_mwh: list[float] = Field(default_factory=list)
    national_load_mw: list[float] = Field(default_factory=list)
    generation_mw_by_carrier: dict[str, list[float]] = Field(default_factory=dict)


class HourlyMarket(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: int
    case_name: str
    network_sha256: str | None = None
    extracted_at_utc: str | None = None
    snapshot_count: int | None = None
    weight_sum_hours: float | None = None
    regions: list[str] = Field(default_factory=list)
    national: NationalMarketPosition = Field(default_factory=NationalMarketPosition)
    by_region: dict[str, RegionMarketPosition] = Field(default_factory=dict)
    network_stress: NetworkStress = Field(default_factory=NetworkStress)
    series: MarketSeries | None = None

    # -- the two questions the rest of the API asks of this layer ----------

    def capture_price(self, region_id: str | None, carrier: str) -> float | None:
        """The price a NEW price-taking plant of this carrier would be paid at
        this region.

        A region with none of that technology installed has no profile of its
        own in the solved network, so the fallback applies the NATIONAL capture
        *rate* to that region's own price level, rather than handing over the
        national capture *price*. The two differ whenever a region's price level
        differs from the country's: the rate is the transferable part (when this
        technology produces, relative to everything else), the level is local.
        `capture_basis` says which of the two a given figure came from."""
        position = self._carrier_at(region_id, carrier)
        if position is not None and position.availability_capture_price_eur_per_mwh is not None:
            return position.availability_capture_price_eur_per_mwh

        national_rate = self._national_capture_rate(carrier)
        if national_rate is None:
            return None
        local_price = self.region_price(region_id)
        if local_price is None:
            return None
        return local_price * national_rate

    def capture_basis(self, region_id: str | None, carrier: str) -> str | None:
        """"region" when the figure comes from this region's own installed
        profile of that technology, "national_shape" when it is the national
        capture rate applied to the region's price level, None when neither
        exists."""
        position = self._carrier_at(region_id, carrier)
        if position is not None and position.availability_capture_price_eur_per_mwh is not None:
            return "region"
        if self._national_capture_rate(carrier) is not None and self.region_price(region_id) is not None:
            return "national_shape"
        return None

    def _national_capture_rate(self, carrier: str) -> float | None:
        national = self.national.carriers.get(carrier)
        reference = self.national.time_weighted_price_eur_per_mwh
        if national is None or not reference:
            return None
        if national.availability_capture_price_eur_per_mwh is None:
            return None
        return national.availability_capture_price_eur_per_mwh / reference

    def capacity_factor_pct(self, region_id: str | None, carrier: str) -> float | None:
        """The region's own availability capacity factor for this carrier --
        the solved network's weather at that location, not a national average.
        Availability, not realised output: a new project is not subject to the
        curtailment the existing fleet there happens to suffer."""
        position = self._carrier_at(region_id, carrier)
        if position is not None and position.availability_capacity_factor_pct is not None:
            return position.availability_capacity_factor_pct

        national = self.national.carriers.get(carrier)
        if national is not None and national.availability_capacity_factor_pct is not None:
            return national.availability_capacity_factor_pct
        return None

    def capture_rate_pct(self, region_id: str | None, carrier: str) -> float | None:
        position = self._carrier_at(region_id, carrier)
        if position is not None and position.capture_rate_pct is not None:
            return position.capture_rate_pct

        capture = self.capture_price(region_id, carrier)
        reference = self.national.time_weighted_price_eur_per_mwh
        if capture is None or not reference:
            return None
        return 100.0 * capture / reference

    def region_price(self, region_id: str | None) -> float | None:
        if region_id is None:
            return self.national.time_weighted_price_eur_per_mwh
        region = self.by_region.get(region_id)
        return region.time_weighted_price_eur_per_mwh if region else None

    def _carrier_at(self, region_id: str | None, carrier: str) -> CarrierMarketPosition | None:
        if region_id is None:
            return self.national.carriers.get(carrier)
        region = self.by_region.get(region_id)
        return region.carriers.get(carrier) if region else None


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def hourly_market_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "generated" / HOURLY_MARKET_DIRNAME


def hourly_market_path(case_name: str) -> Path:
    return hourly_market_dir() / f"{case_name}.json"


@lru_cache(maxsize=16)
def get_hourly_market(case_name: str) -> HourlyMarket | None:
    """The extracted hourly layer for a case, or None when it has not been
    extracted. None is a normal state, never an error: a case solved after the
    last extraction run simply has no hourly layer yet, and every caller must
    degrade to the annual averages rather than fail."""
    path = hourly_market_path(case_name)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return HourlyMarket(**raw)


def available_cases() -> list[str]:
    directory = hourly_market_dir()
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))
