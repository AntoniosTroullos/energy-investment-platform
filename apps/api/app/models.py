from typing import Literal

from pydantic import BaseModel, Field


BudgetTier = Literal["small", "medium", "large"]
PreferredTechnology = Literal["all", "solar", "wind"]
ConnectionCostLevel = Literal["Low", "Medium", "High"]


class Scenario(BaseModel):
    budgetTier: BudgetTier
    preferredTechnology: PreferredTechnology
    maxConnectionDistanceKm: float = Field(ge=5, le=25)
    excludeLandConstrained: bool
    minInvestmentScore: float = Field(ge=0, le=100)


class ScenarioEvaluationRequest(BaseModel):
    scenario: Scenario


class TopCandidateSummary(BaseModel):
    id: str
    technology: str
    investmentScore: float
    distanceToSubstationKm: float
    distanceToLineKm: float
    connectionCostLevel: str
    landExcluded: bool


class ScoreStats(BaseModel):
    min: float
    max: float
    average: float


class TechnologyBreakdown(BaseModel):
    solar: int
    wind: int


class ScenarioEvaluationResponse(BaseModel):
    eligibleCount: int
    topCandidateIds: list[str]
    summary: str
    topCandidates: list[TopCandidateSummary]
    scoreStats: ScoreStats
    technologyBreakdown: TechnologyBreakdown


class ClimateCurrentConditions(BaseModel):
    time: str
    temperatureC: float | None = None
    cloudCoverPct: float | None = None
    windSpeed10mKph: float | None = None
    windSpeed100mKph: float | None = None
    shortwaveRadiationWm2: float | None = None
    directNormalIrradianceWm2: float | None = None


class ClimateEfficiencyEstimate(BaseModel):
    modeledTechnology: str
    estimatedEfficiencyPct: float | None = None
    band: str
    summary: str


class ClimateAssetResponse(BaseModel):
    source: str
    latitude: float
    longitude: float
    assetTechnology: str
    current: ClimateCurrentConditions
    efficiency: ClimateEfficiencyEstimate


class MarketFlowItem(BaseModel):
    zone: str
    direction: str
    powerMw: float


class MarketPriceSignal(BaseModel):
    valueEurMwh: float | None = None
    datetime: str | None = None
    temporalGranularity: str | None = None
    label: str = "Current operational price"


class GreeceMarketSignalResponse(BaseModel):
    source: str
    zone: str
    status: str
    currentPrice: MarketPriceSignal
    totalImportMw: float
    totalExportMw: float
    netImportMw: float
    flows: list[MarketFlowItem]
    summary: str


class RegionalDemandRow(BaseModel):
    regionId: str
    geo: str
    allocatedLoadMw: float
    allocationShare: float
    residentialShare: float
    commercialShare: float
    industrialShare: float
    agriculturalShare: float
    publicShare: float
    dominantDriver: str
    month: int
    season: str


class RegionalDemandAllocationResponse(BaseModel):
    timestampUtc: str
    nationalLoadMw: float
    month: int
    season: str
    method: str
    source: str
    regions: list[RegionalDemandRow]
    regionsGeojson: dict


class CandidateCell(BaseModel):
    id: str
    name: str
    technology: str
    solar_score: float
    wind_score: float
    distance_to_substation_km: float
    distance_to_line_km: float
    excluded: bool = False
    land_excluded: bool
    connection_cost_level: ConnectionCostLevel
    status: str
    investment_score: float
    geometry: dict
    # Fraction of the cell's grid square left buildable after land-constraint
    # clipping (pipeline/generate_candidates.py) -- not read by the existing
    # screening filter, but needed by investment_analysis.py to size an
    # assumed installed capacity for the buildable land that remains.
    buildable_fraction: float | None = None


class CandidateInvestmentAnalysis(BaseModel):
    """One candidate cell's real-data-grounded financial analysis for a given
    solved PyPSA scenario -- see app/investment_analysis.py. Every field this
    module cannot compute becomes `message`, never a silently dropped row."""

    candidate_id: str
    technology: str
    carrier: str | None = None
    region_id: str | None = None
    assumed_capacity_mw: float | None = None
    capex_eur: float | None = None
    annual_generation_year0_mwh: float | None = None
    captured_price_eur_per_mwh: float | None = None
    lcoe_eur_per_mwh: float | None = None
    npv_eur: float | None = None
    irr_pct: float | None = None
    payback_years: float | None = None
    message: str | None = None


class CandidateInvestmentAnalysisResponse(BaseModel):
    case_name: str
    target_year: int
    analyses: list[CandidateInvestmentAnalysis]
    # Plain-language notes on every assumption/proxy this analysis relies on
    # (power density, capacity-factor methodology, captured-price proxy, cost
    # data source) -- rendered as a permanent disclosure by the frontend, not
    # left implicit.
    assumptions: dict[str, str]


class PortfolioAnalysisRequest(BaseModel):
    case_name: str
    candidate_ids: list[str]


class PortfolioCandidateSummary(BaseModel):
    """One requested candidate's contribution to the portfolio -- present for
    EVERY requested id, including one that doesn't exist or that couldn't be
    fully computed (via `message`), never silently dropped."""

    candidate_id: str
    technology: str
    carrier: str | None = None
    region_id: str | None = None
    assumed_capacity_mw: float | None = None
    capex_eur: float | None = None
    npv_eur: float | None = None
    irr_pct: float | None = None
    message: str | None = None


class PortfolioBreakdownEntry(BaseModel):
    label: str
    capex_eur: float
    assumed_capacity_mw: float
    candidate_count: int
    capex_share_pct: float


class PortfolioAnalysisResponse(BaseModel):
    case_name: str
    target_year: int
    candidates: list[PortfolioCandidateSummary]
    included_count: int
    excluded_count: int
    total_capex_eur: float | None = None
    total_assumed_capacity_mw: float | None = None
    # Sum of each included candidate's own NPV -- valid regardless of
    # differing lifetimes/discount rates across technologies.
    total_npv_eur: float | None = None
    # NOT a weighted average of each candidate's own IRR (averaging IRRs
    # across investments is not mathematically valid) -- computed from the
    # combined annual cash-flow stream. See app/investment_analysis.py's
    # combine_cash_flows.
    portfolio_irr_pct: float | None = None
    portfolio_payback_years: float | None = None
    technology_breakdown: list[PortfolioBreakdownEntry]
    region_breakdown: list[PortfolioBreakdownEntry]
    concentration_flags: list[str]
    assumptions: dict[str, str]
