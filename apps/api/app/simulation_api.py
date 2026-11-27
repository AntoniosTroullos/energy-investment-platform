"""Request and response models for the hour-by-hour simulation endpoints.

A year of hourly traces is about 60 KB per series, and a response carrying
four of them for twenty-five years would be useless to a browser. So every
simulation returns its annual rows in full and exactly one week of hourly
detail: by default the week containing the year's highest price, because that
is the week where a battery makes its money and a flexible industrial site
earns its contract. A caller that wants a different week asks for it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

HOURS_PER_WEEK = 168


class HourlyWindow(BaseModel):
    """One week of hourly detail, with the reason it was chosen."""

    start_hour: int
    label: str
    timestamps: list[str] = Field(default_factory=list)
    price_eur_per_mwh: list[float] = Field(default_factory=list)
    output_mw: list[float] = Field(default_factory=list)
    state_of_charge_mwh: list[float] = Field(default_factory=list)


class SimulatedYearOut(BaseModel):
    year_index: int
    generation_mwh: float
    curtailed_mwh: float
    revenue_eur: float
    capture_price_eur_per_mwh: float | None = None
    capacity_factor_pct: float
    hours_producing: int
    hours_curtailed: int
    output_retention_pct: float


class StorageYearOut(BaseModel):
    year_index: int
    capacity_retention_pct: float
    usable_energy_mwh: float
    energy_charged_mwh: float
    energy_discharged_mwh: float
    charging_cost_eur: float
    discharge_revenue_eur: float
    cycle_cost_eur: float
    gross_margin_eur: float
    equivalent_full_cycles: float
    hours_charging: int
    hours_discharging: int
    negative_price_hours_charged: int
    average_charge_price_eur_per_mwh: float | None = None
    average_discharge_price_eur_per_mwh: float | None = None


class PriceYearSummary(BaseModel):
    year: int
    source: str
    redistribution_allowed: bool
    hours: int
    missing_hours: int
    mean_eur_per_mwh: float
    min_eur_per_mwh: float
    max_eur_per_mwh: float
    negative_hours: int
    zero_or_negative_hours: int


class AssetSimulationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    kind: str
    carrier: str
    capacity_mw: float
    price_year: int
    price_source: str
    lifetime_years: int

    years: list[SimulatedYearOut] = Field(default_factory=list)
    storage_years: list[StorageYearOut] = Field(default_factory=list)

    capex_eur: float | None = None
    npv_eur: float | None = None
    irr_pct: float | None = None
    payback_years: float | None = None
    lifetime_revenue_eur: float = 0.0

    price_summary: PriceYearSummary | None = None
    window: HourlyWindow | None = None
    notes: list[str] = Field(default_factory=list)


# --- requests --------------------------------------------------------------


class GenerationSimulationRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    carrier: str = Field(pattern="^(solar|wind)$")
    capacity_mw: float = Field(gt=0, le=2000)
    price_year: int = Field(default=2025, ge=2015, le=2030)
    lifetime_years: int = Field(default=25, ge=1, le=40)
    capex_eur_per_kw: float | None = Field(default=None, ge=0)
    fixed_opex_pct_of_capex: float = Field(default=2.0, ge=0, le=20)
    discount_rate_pct: float = Field(default=7.0, ge=0, le=30)
    price_escalation_pct_per_year: float = Field(default=0.0, ge=-10, le=10)
    # A merchant plant stops when the price goes below zero. One on a contract
    # for difference does not, and the difference is worth seeing.
    curtail_at_negative_prices: bool = True
    window_start_hour: int | None = Field(default=None, ge=0, lt=8760)


class StorageSimulationRequest(BaseModel):
    power_mw: float = Field(gt=0, le=1000)
    energy_capacity_mwh: float = Field(gt=0, le=10000)
    round_trip_efficiency: float = Field(default=0.88, gt=0.3, le=1.0)
    min_soc_fraction: float = Field(default=0.05, ge=0, lt=1)
    max_soc_fraction: float = Field(default=0.95, gt=0, le=1)
    cycle_cost_eur_per_mwh: float = Field(default=6.0, ge=0, le=200)
    grid_charge_eur_per_mwh: float = Field(default=0.0, ge=0, le=200)
    max_cycles_per_day: float = Field(default=1.5, gt=0, le=10)
    calendar_fade_pct_per_year: float = Field(default=1.5, ge=0, le=10)
    cycle_fade_pct_per_equivalent_cycle: float = Field(default=0.005, ge=0, le=1)

    price_year: int = Field(default=2025, ge=2015, le=2030)
    lifetime_years: int = Field(default=15, ge=1, le=40)
    capex_eur_per_kwh: float | None = Field(default=None, ge=0)
    fixed_opex_pct_of_capex: float = Field(default=2.0, ge=0, le=20)
    discount_rate_pct: float = Field(default=8.0, ge=0, le=30)
    price_escalation_pct_per_year: float = Field(default=0.0, ge=-10, le=10)
    window_start_hour: int | None = Field(default=None, ge=0, lt=8760)


class InterruptibilityContractIn(BaseModel):
    product: str = Field(default="type_1", pattern="^(type_1|type_2)$")
    contracted_mw: float = Field(gt=0, le=2000)
    availability_price_eur_per_mw_year: float | None = Field(default=None, ge=0)
    activation_price_eur_per_mwh: float = Field(default=0.0, ge=0)
    max_activation_hours_per_year: float | None = Field(default=None, ge=0)
    max_activations_per_year: int = Field(default=20, ge=0, le=500)
    max_duration_hours: int = Field(default=4, ge=1, le=24)
    min_hours_between_activations: int = Field(default=120, ge=0, le=8760)


class DemandResponseRequest(BaseModel):
    name: str = "Industrial site"
    # Either a flat continuous process or a two-shift pattern, unless the
    # caller supplies its own 8,760-hour profile.
    profile: str = Field(default="continuous", pattern="^(continuous|two_shift|custom)$")
    average_load_mw: float = Field(default=50.0, gt=0, le=2000)
    base_load_mw: float = Field(default=10.0, ge=0, le=2000)
    custom_load_mw: list[float] | None = None

    interruptible_fraction: float = Field(default=0.3, ge=0, le=1)
    production_loss_eur_per_mwh: float = Field(default=0.0, ge=0, le=10000)
    rebound_fraction: float = Field(default=0.0, ge=0, le=1)
    shiftable_fraction: float = Field(default=0.0, ge=0, le=1)

    price_year: int = Field(default=2025, ge=2015, le=2030)
    contracts: list[InterruptibilityContractIn] = Field(default_factory=list)


class ActivationEventOut(BaseModel):
    start_hour: int
    duration_hours: int
    energy_not_consumed_mwh: float
    payment_eur: float
    avoided_energy_cost_eur: float
    production_loss_eur: float
    price_at_activation_eur_per_mwh: float


class DemandResponseResponse(BaseModel):
    site_name: str
    year: int
    price_source: str

    annual_consumption_mwh: float
    baseline_energy_cost_eur: float

    availability_revenue_eur: float
    activation_revenue_eur: float
    avoided_energy_cost_eur: float
    load_shifting_saving_eur: float
    production_loss_eur: float
    rebound_cost_eur: float
    net_benefit_eur: float
    net_benefit_pct_of_energy_bill: float | None = None

    activation_count: int
    activation_hours: float
    energy_not_consumed_mwh: float

    events: list[ActivationEventOut] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
