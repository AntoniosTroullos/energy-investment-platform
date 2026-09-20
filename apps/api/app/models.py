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
