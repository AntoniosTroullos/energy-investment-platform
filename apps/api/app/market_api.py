"""Response models for the live market layer.

Kept apart from app/models.py, which carries the older camelCase market signal
models, because everything built since (overview, simulation, and this) speaks
snake_case end to end and the web client's generated types follow suit.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FeedStateOut(BaseModel):
    """One source's freshness. See app/market_feeds.py for why cadence, lag and
    status are three separate things."""

    key: str
    label: str
    source: str
    status: str  # live | stale | unavailable
    what_it_is_for: str
    cadence_minutes: int
    expected_lag_minutes: int
    refreshed_at_utc: str | None = None
    age_minutes: float | None = None
    covers_to_utc: str | None = None
    # Negative for a feed that publishes ahead of real time, as day-ahead does.
    lag_minutes: float | None = None
    detail: str | None = None


class ReserveRequirementOut(BaseModel):
    product: str
    mean_mw: float
    max_mw: float
    min_mw: float


class StorageFleetBehaviourOut(BaseModel):
    """What Greece's operating storage fleet was scheduled to do on the day,
    valued at the balancing prices of the same quarter-hours.

    This is the platform's only real-world check on its own storage model: a
    simulated battery's charge and discharge prices should land in the same
    territory as the fleet's."""

    units: int
    periods_charging: int
    periods_discharging: int
    charged_mwh: float
    discharged_mwh: float
    average_charge_price_eur_per_mwh: float | None = None
    average_discharge_price_eur_per_mwh: float | None = None
    round_trip_spread_eur_per_mwh: float | None = None


class ImbalanceStatisticsOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    periods: int
    from_utc: str | None = None
    to_utc: str | None = None
    mean_eur_per_mwh: float
    median_eur_per_mwh: float
    p10_eur_per_mwh: float
    p90_eur_per_mwh: float
    min_eur_per_mwh: float
    max_eur_per_mwh: float
    negative_periods: int
    system_short_periods: int
    system_long_periods: int
    mean_price_when_short_eur_per_mwh: float | None = None
    mean_price_when_long_eur_per_mwh: float | None = None
    short_long_spread_eur_per_mwh: float | None = None
    activated_up_mwh: float | None = None
    activated_down_mwh: float | None = None


class MfrrStatisticsOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    mean_up_eur_per_mwh: float
    mean_down_eur_per_mwh: float
    median_up_eur_per_mwh: float
    median_down_eur_per_mwh: float
    max_up_eur_per_mwh: float
    min_down_eur_per_mwh: float
    mean_spread_eur_per_mwh: float
    negative_down_periods: int


class PricingAttributionOut(BaseModel):
    """Which price set settlement, measured rather than assumed -- see the
    `balancing.pricing_attribution` docstring."""

    periods: int
    set_by_mfrr_up: int
    set_by_mfrr_down: int
    set_by_neither: int
    set_by_mfrr_up_pct: float
    set_by_mfrr_down_pct: float
    set_by_neither_pct: float


class BalancingDayOut(BaseModel):
    """The operator's own schedule for the most recent market day."""

    file_name: str
    periods: int
    from_utc: str
    to_utc: str
    timestamps_utc: list[str] = Field(default_factory=list)
    price_up_eur_per_mwh: list[float | None] = Field(default_factory=list)
    price_down_eur_per_mwh: list[float | None] = Field(default_factory=list)
    system_load_mw: list[float | None] = Field(default_factory=list)
    renewables_mw: list[float | None] = Field(default_factory=list)
    storage_mw: list[float | None] = Field(default_factory=list)
    mean_price_up_eur_per_mwh: float | None = None
    mean_price_down_eur_per_mwh: float | None = None
    reserve_requirements: list[ReserveRequirementOut] = Field(default_factory=list)
    storage_fleet: StorageFleetBehaviourOut | None = None


class BalancingYearSummaryOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    from_utc: str
    to_utc: str
    hours: int
    missing_hours: int
    files_used: int
    mean_eur_per_mwh: float
    median_eur_per_mwh: float
    p10_eur_per_mwh: float
    p90_eur_per_mwh: float
    min_eur_per_mwh: float
    max_eur_per_mwh: float
    negative_hours: int
    # What hourly averaging of the settled quarter-hours discards. A real
    # battery can trade inside the hour, so this is revenue the hourly
    # simulation cannot see -- which makes its storage figures conservative.
    mean_intra_hour_spread_eur_per_mwh: float
    source: str


class DayAheadComparisonOut(BaseModel):
    """Day-ahead against settled balancing over a comparable window.

    The headline of the whole live-market layer: a battery valued on day-ahead
    is valued in the wrong market, and this says by how much."""

    day_ahead_year: int | None = None
    day_ahead_mean_eur_per_mwh: float | None = None
    day_ahead_negative_hours: int | None = None
    balancing_mean_eur_per_mwh: float | None = None
    balancing_negative_hours: int | None = None
    negative_hour_ratio: float | None = None
    mean_premium_eur_per_mwh: float | None = None


class LiveMarketResponse(BaseModel):
    """Everything the live market layer knows, with every number's source and
    freshness attached."""

    generated_at_utc: str
    feeds: list[FeedStateOut] = Field(default_factory=list)
    imbalance: ImbalanceStatisticsOut | None = None
    mfrr: MfrrStatisticsOut | None = None
    pricing_attribution: PricingAttributionOut | None = None
    settlement_file: str | None = None
    day: BalancingDayOut | None = None
    trailing_year: BalancingYearSummaryOut | None = None
    comparison: DayAheadComparisonOut | None = None
    notes: list[str] = Field(default_factory=list)
