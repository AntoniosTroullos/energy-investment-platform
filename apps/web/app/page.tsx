"use client";

import { useEffect, useMemo, useState } from "react";
import AnalysisFiltersPanel from "../components/AnalysisFiltersPanel";
import AssetDetailsDrawer from "../components/AssetDetailsDrawer";
import ClimatePanel from "../components/ClimatePanel";
import ComparePanel from "../components/ComparePanel";
import InfrastructureFiltersPanel from "../components/InfrastructureFiltersPanel";
import LayerControlPanel from "../components/LayerControlPanel";
import MarketPanel from "../components/MarketPanel";
import ModeToggle, { type ViewMode } from "../components/ModeToggle";
import ScenarioResultsSourcePanel from "../components/ScenarioResultsSourcePanel";
import {
  getGeneratorClustersGeoJson,
  getScenarioRegionsGeoJson,
} from "../lib/pypsaScenario/pypsaScenario.api";
import SearchPanel from "../components/SearchPanel";
import TopOpportunitiesPanel from "../components/TopOpportunitiesPanel";
import { useScenarioConfig } from "../lib/scenario/ScenarioConfigContext";
import {
  getEligibleCandidateCells,
  matchesCandidateScenario,
  sortCandidatesByInvestmentScore,
} from "../lib/scenario/candidate-screening";
import MapView from "../components/MapView";
import { buildSelections } from "../data/assets";
import { apiUrl } from "../lib/config";
import { assetSelectionsToFeatureCollection, emptyFeatureCollection } from "../lib/geojson";
import { alignGasPipelineRoutes } from "../lib/infrastructure-alignment";
import { isCandidateExcludedByNatura } from "../lib/natura-exclusion";
import {
  PLANT_STATUS_CATEGORIES,
  PLANT_TECHNOLOGY_CATEGORIES,
  addPlantExplorerProperties,
  filterPlantAssets,
  isDisplayablePlantAsset,
  matchesPlantStatus,
  matchesPlantTechnology,
  type PlantStatusCategory,
  type PlantTechnologyCategory,
} from "../lib/plant-categories";
import {
  filterAssetsByVoltage,
  getVoltageOptions,
  matchesVoltageFilter,
} from "../lib/voltage";
import { getAssetsInViewCount, isAssetInViewport } from "../lib/viewport-geometry";
import type {
  AssetSelection,
  FocusRequest,
  ViewportBounds,
} from "../types/asset";
import type {
  ClimateAssetResponse,
  ClimateRequestState,
} from "../types/climate";
import type {
  GreeceMarketSignalResponse,
  MarketFlowDirection,
  MarketRequestState,
} from "../types/market";
import type { Scenario } from "../lib/scenario/scenario.types";

const CANDIDATES_API_URL = apiUrl("/candidates");
const PLANTS_API_URL = apiUrl("/plants");
const SUBSTATIONS_API_URL = apiUrl("/substations");
const TRANSMISSION_LINES_API_URL = apiUrl("/transmission-lines");
const GAS_PIPELINES_API_URL = apiUrl("/gas-pipelines");
const GAS_IMPORT_POINTS_API_URL = apiUrl("/gas-import-points");
const HYDROGEN_PIPELINES_API_URL = apiUrl("/hydrogen-pipelines");
const HYDROGEN_PROJECTS_API_URL = apiUrl("/hydrogen-projects");
const NATURA_2000_API_URL = apiUrl("/natura-2000");
const CLIMATE_ASSET_API_URL = apiUrl("/climate/asset");
const MARKET_GREECE_API_URL = apiUrl("/market/greece");
const MARKET_GREECE_BOUNDARY_API_URL = apiUrl("/market/greece-boundary");

type CandidateLoadState = "idle" | "loading" | "success" | "error";
type InfrastructureLoadState = "idle" | "loading" | "success" | "error";

export default function Home() {
  const { scenario } = useScenarioConfig();
  const [viewMode, setViewMode] = useState<ViewMode>("explorer");
  const [showPlants, setShowPlants] = useState(true);
  const [showSubstations, setShowSubstations] = useState(true);
  const [showLines, setShowLines] = useState(true);
  const [showGasPipelines, setShowGasPipelines] = useState(true);
  const [showGasImports, setShowGasImports] = useState(true);
  const [showHydrogenPipelines, setShowHydrogenPipelines] = useState(true);
  const [showHydrogenProjects, setShowHydrogenProjects] = useState(true);
  const [showNatura2000, setShowNatura2000] = useState(false);
  const [showCells, setShowCells] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState<AssetSelection | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  const [comparedAssets, setComparedAssets] = useState<AssetSelection[]>([]);
  const [candidateCellAssets, setCandidateCellAssets] = useState<AssetSelection[]>([]);
  const [candidateLoadState, setCandidateLoadState] =
    useState<CandidateLoadState>("idle");
  const [candidateLoadErrorMessage, setCandidateLoadErrorMessage] = useState("");
  const [allPlantAssets, setAllPlantAssets] = useState<AssetSelection[]>([]);
  const [substationAssets, setSubstationAssets] = useState<AssetSelection[]>([]);
  const [lineAssets, setLineAssets] = useState<AssetSelection[]>([]);
  const [gasPipelineAssets, setGasPipelineAssets] = useState<AssetSelection[]>([]);
  const [gasImportPointAssets, setGasImportPointAssets] = useState<AssetSelection[]>([]);
  const [hydrogenPipelineAssets, setHydrogenPipelineAssets] = useState<AssetSelection[]>([]);
  const [hydrogenProjectAssets, setHydrogenProjectAssets] = useState<AssetSelection[]>([]);
  const [natura2000Data, setNatura2000Data] =
    useState<GeoJSON.FeatureCollection>(emptyFeatureCollection);
  const [excludeNatura2000, setExcludeNatura2000] = useState(false);
  const [enabledPlantTechnologies, setEnabledPlantTechnologies] = useState<
    PlantTechnologyCategory[]
  >(PLANT_TECHNOLOGY_CATEGORIES);
  const [enabledPlantStatuses, setEnabledPlantStatuses] = useState<
    PlantStatusCategory[]
  >(PLANT_STATUS_CATEGORIES);
  const [voltageFilter, setVoltageFilter] = useState("all");
  const [limitResultsToViewport, setLimitResultsToViewport] = useState(false);
  const [viewportBounds, setViewportBounds] = useState<ViewportBounds | null>(null);
  const [infrastructureLoadState, setInfrastructureLoadState] =
    useState<InfrastructureLoadState>("idle");
  const [infrastructureLoadErrorMessage, setInfrastructureLoadErrorMessage] =
    useState("");
  const [assetClimate, setAssetClimate] = useState<ClimateAssetResponse | null>(null);
  const [climateRequestState, setClimateRequestState] =
    useState<ClimateRequestState>("idle");
  const [climateErrorMessage, setClimateErrorMessage] = useState("");
  const [marketHighlightEnabled, setMarketHighlightEnabled] = useState(false);
  const [marketSignal, setMarketSignal] =
    useState<GreeceMarketSignalResponse | null>(null);
  const [marketRequestState, setMarketRequestState] =
    useState<MarketRequestState>("idle");
  const [marketErrorMessage, setMarketErrorMessage] = useState("");
  const [marketZoneData, setMarketZoneData] =
    useState<GeoJSON.FeatureCollection>(emptyFeatureCollection);
  const [selectedScenarioCaseName, setSelectedScenarioCaseName] = useState<string | null>(null);
  const [showGeneratorClusters, setShowGeneratorClusters] = useState(false);
  const [generatorClustersData, setGeneratorClustersData] =
    useState<GeoJSON.FeatureCollection>(emptyFeatureCollection);
  const [showScenarioRegions, setShowScenarioRegions] = useState(false);
  const [scenarioRegionsData, setScenarioRegionsData] =
    useState<GeoJSON.FeatureCollection>(emptyFeatureCollection);

  useEffect(() => {
    void loadCandidateCells();
  }, []);

  useEffect(() => {
    void loadPilotInfrastructure();
  }, []);

  useEffect(() => {
    void loadMarketZoneBoundary();
  }, []);

  useEffect(() => {
    void loadGeneratorClusters();
  }, []);

  useEffect(() => {
    if (!selectedScenarioCaseName) {
      setScenarioRegionsData(emptyFeatureCollection);
      return;
    }

    void loadScenarioRegions(selectedScenarioCaseName);
  }, [selectedScenarioCaseName]);

  useEffect(() => {
    const pointCoordinates = getPointCoordinates(selectedAsset);

    if (!selectedAsset || selectedAsset.assetType !== "plant" || !pointCoordinates) {
      setAssetClimate(null);
      setClimateRequestState("idle");
      setClimateErrorMessage("");
      return;
    }

    const controller = new AbortController();
    void loadAssetClimate(selectedAsset, pointCoordinates, controller.signal);

    return () => controller.abort();
  }, [selectedAsset]);

  useEffect(() => {
    if (!marketHighlightEnabled) {
      return;
    }

    void loadMarketSignal();
    const intervalId = window.setInterval(() => {
      void loadMarketSignal();
    }, 15 * 60 * 1000);

    return () => window.clearInterval(intervalId);
  }, [marketHighlightEnabled]);

  const visibilityState = {
    plants: [showPlants, setShowPlants],
    substations: [showSubstations, setShowSubstations],
    lines: [showLines, setShowLines],
    gasPipelines: [showGasPipelines, setShowGasPipelines],
    gasImports: [showGasImports, setShowGasImports],
    hydrogenPipelines: [showHydrogenPipelines, setShowHydrogenPipelines],
    hydrogenProjects: [showHydrogenProjects, setShowHydrogenProjects],
    natura2000: [showNatura2000, setShowNatura2000],
    cells: [showCells, setShowCells],
    generatorClusters: [showGeneratorClusters, setShowGeneratorClusters],
    scenarioRegions: [showScenarioRegions, setShowScenarioRegions],
  } as const;

  const isExplorerMode = viewMode === "explorer";

  // Memoized because these derive from potentially large datasets (15k+ plants,
  // 3k+ substations in production data) and must not re-run on every render —
  // e.g. every search-box keystroke or scenario slider drag.
  const normalizedPlantAssets = useMemo(
    () => allPlantAssets.map(addPlantExplorerProperties),
    [allPlantAssets],
  );
  const plantAssets = useMemo(
    () =>
      filterPlantAssets(
        normalizedPlantAssets,
        enabledPlantTechnologies,
        enabledPlantStatuses,
      ),
    [normalizedPlantAssets, enabledPlantTechnologies, enabledPlantStatuses],
  );
  const voltageOptions = useMemo(
    () => getVoltageOptions([...substationAssets, ...lineAssets]),
    [substationAssets, lineAssets],
  );
  const filteredSubstationAssets = useMemo(
    () => filterAssetsByVoltage(substationAssets, voltageFilter),
    [substationAssets, voltageFilter],
  );
  const filteredLineAssets = useMemo(
    () => filterAssetsByVoltage(lineAssets, voltageFilter),
    [lineAssets, voltageFilter],
  );
  const plantsData = useMemo(
    () => assetSelectionsToFeatureCollection(plantAssets),
    [plantAssets],
  );
  const filteredSubstationsData = useMemo(
    () => assetSelectionsToFeatureCollection(filteredSubstationAssets),
    [filteredSubstationAssets],
  );
  const filteredLinesData = useMemo(
    () => assetSelectionsToFeatureCollection(filteredLineAssets),
    [filteredLineAssets],
  );
  const gasPipelinesData = useMemo(
    () => assetSelectionsToFeatureCollection(gasPipelineAssets),
    [gasPipelineAssets],
  );
  const gasImportPointsData = useMemo(
    () => assetSelectionsToFeatureCollection(gasImportPointAssets),
    [gasImportPointAssets],
  );
  const hydrogenPipelinesData = useMemo(
    () => assetSelectionsToFeatureCollection(hydrogenPipelineAssets),
    [hydrogenPipelineAssets],
  );
  const hydrogenProjectsData = useMemo(
    () => assetSelectionsToFeatureCollection(hydrogenProjectAssets),
    [hydrogenProjectAssets],
  );

  const visibleSelectedAsset = getVisibleSelectedAsset(selectedAsset, {
    viewMode,
    showPlants,
    showSubstations,
    showLines,
    showGasPipelines,
    showGasImports,
    showHydrogenPipelines,
    showHydrogenProjects,
    showNatura2000,
    showCells,
    enabledPlantTechnologies,
    enabledPlantStatuses,
    voltageFilter,
    scenario,
    excludeNatura2000,
    natura2000Data,
  });

  const infrastructureAssets = useMemo(
    () => [
      ...plantAssets,
      ...filteredSubstationAssets,
      ...filteredLineAssets,
      ...gasPipelineAssets,
      ...gasImportPointAssets,
      ...hydrogenPipelineAssets,
      ...hydrogenProjectAssets,
    ],
    [
      plantAssets,
      filteredSubstationAssets,
      filteredLineAssets,
      gasPipelineAssets,
      gasImportPointAssets,
      hydrogenPipelineAssets,
      hydrogenProjectAssets,
    ],
  );
  const plantsInViewCount = useMemo(
    () => getAssetsInViewCount(plantAssets, viewportBounds),
    [plantAssets, viewportBounds],
  );
  const substationsInViewCount = useMemo(
    () => getAssetsInViewCount(filteredSubstationAssets, viewportBounds),
    [filteredSubstationAssets, viewportBounds],
  );
  const linesInViewCount = useMemo(
    () => getAssetsInViewCount(filteredLineAssets, viewportBounds),
    [filteredLineAssets, viewportBounds],
  );
  const gasPipelinesInViewCount = useMemo(
    () => getAssetsInViewCount(gasPipelineAssets, viewportBounds),
    [gasPipelineAssets, viewportBounds],
  );
  const gasImportsInViewCount = useMemo(
    () => getAssetsInViewCount(gasImportPointAssets, viewportBounds),
    [gasImportPointAssets, viewportBounds],
  );
  const hydrogenPipelinesInViewCount = useMemo(
    () => getAssetsInViewCount(hydrogenPipelineAssets, viewportBounds),
    [hydrogenPipelineAssets, viewportBounds],
  );
  const hydrogenProjectsInViewCount = useMemo(
    () => getAssetsInViewCount(hydrogenProjectAssets, viewportBounds),
    [hydrogenProjectAssets, viewportBounds],
  );
  const filteredCellAssets = useMemo(
    () =>
      getEligibleCandidateCells(candidateCellAssets, scenario).filter(
        (asset) => !isCandidateExcludedByNatura(asset, natura2000Data, excludeNatura2000),
      ),
    [candidateCellAssets, scenario, natura2000Data, excludeNatura2000],
  );
  const filteredCellsData = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: filteredCellAssets.map((asset) => asset.feature),
    }),
    [filteredCellAssets],
  );

  const topOpportunities = useMemo(
    () => getTopOpportunities(filteredCellAssets),
    [filteredCellAssets],
  );
  const marketFlowDirection = getMarketFlowDirection(marketSignal);

  const query = searchQuery.trim().toLowerCase();
  const searchableInfrastructureAssets = useMemo(
    () =>
      limitResultsToViewport
        ? infrastructureAssets.filter((asset) => isAssetInViewport(asset, viewportBounds))
        : infrastructureAssets,
    [infrastructureAssets, limitResultsToViewport, viewportBounds],
  );
  const searchResults = useMemo(() => {
    if (!query) {
      return [];
    }

    return searchableInfrastructureAssets.filter((asset) => {
      const searchableValues = [
        asset.name,
        asset.id,
        asset.properties.technology,
        asset.properties.technology_category,
        asset.properties.technology_label,
        asset.properties.status,
        asset.properties.nominal_capacity_mw,
        asset.properties.voltage_kv,
        asset.properties.operator,
        asset.properties.primary_source,
        asset.properties.region,
        asset.properties.regional_unit,
        asset.properties.municipality,
        asset.properties.pipeline_role,
        asset.properties.pipeline_code,
        asset.properties.pipeline_category,
        asset.properties.development_stage,
        asset.properties.capacity_gwh_per_day,
        asset.properties.length_km,
        asset.properties.estimated_cost_eur,
        asset.properties.import_type,
        asset.properties.project_type,
        asset.properties.hydrogen_role,
        asset.properties.hydrogen_type,
        asset.properties.electrolyzer_capacity_mw,
        asset.properties.annual_output_tpa,
        asset.properties.connected_system,
      ];

      return searchableValues.some((value) =>
        value !== undefined && value !== null
          ? String(value).toLowerCase().includes(query)
          : false,
      );
    });
  }, [searchableInfrastructureAssets, query]);

  return (
    <main className="flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-zinc-950 text-zinc-100">
      <aside className="flex h-full w-80 shrink-0 flex-col overflow-y-auto border-r border-white/10 bg-zinc-900 px-6 py-8">
        {(candidateLoadState === "error" || infrastructureLoadState === "error") && (
          <div className="mb-4 rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3 text-xs text-rose-300">
            {infrastructureLoadState === "error"
              ? infrastructureLoadErrorMessage
              : candidateLoadErrorMessage}
          </div>
        )}

        <ModeToggle mode={viewMode} onChange={handleViewModeChange} />

        <LayerControlPanel mode={viewMode} visibilityState={visibilityState} />

        <ScenarioResultsSourcePanel
          selectedCaseName={selectedScenarioCaseName}
          onSelectCaseName={setSelectedScenarioCaseName}
        />

        <InfrastructureFiltersPanel
          enabledPlantTechnologies={enabledPlantTechnologies}
          onTogglePlantTechnology={togglePlantTechnology}
          enabledPlantStatuses={enabledPlantStatuses}
          onTogglePlantStatus={togglePlantStatus}
          voltageFilter={voltageFilter}
          onVoltageFilterChange={setVoltageFilter}
          voltageOptions={voltageOptions}
          limitResultsToViewport={limitResultsToViewport}
          onLimitResultsToViewportChange={setLimitResultsToViewport}
          plantsInViewCount={plantsInViewCount}
          substationsInViewCount={substationsInViewCount}
          linesInViewCount={linesInViewCount}
          gasPipelinesInViewCount={gasPipelinesInViewCount}
          gasImportsInViewCount={gasImportsInViewCount}
          hydrogenPipelinesInViewCount={hydrogenPipelinesInViewCount}
          hydrogenProjectsInViewCount={hydrogenProjectsInViewCount}
        />

        <ClimatePanel
          asset={selectedAsset}
          climate={assetClimate}
          requestState={climateRequestState}
          errorMessage={climateErrorMessage}
        />

        <MarketPanel
          enabled={marketHighlightEnabled}
          marketSignal={marketSignal}
          requestState={marketRequestState}
          errorMessage={marketErrorMessage}
          onToggle={setMarketHighlightEnabled}
          onRefresh={loadMarketSignal}
        />

        <SearchPanel
          searchQuery={searchQuery}
          onSearchQueryChange={setSearchQuery}
          limitResultsToViewport={limitResultsToViewport}
          searchResults={searchResults}
          onAssetFocus={handleAssetFocus}
        />

        {!isExplorerMode ? (
          <AnalysisFiltersPanel
            excludeNatura2000={excludeNatura2000}
            onExcludeNatura2000Change={handleExcludeNatura2000Change}
          />
        ) : null}

        {!isExplorerMode ? (
          <TopOpportunitiesPanel
            topOpportunities={topOpportunities}
            onAssetFocus={handleAssetFocus}
          />
        ) : null}

        {!isExplorerMode ? (
        <ComparePanel
          comparedAssets={comparedAssets}
          scenario={scenario}
          onFocusAsset={handleAssetFocus}
          onRemoveAsset={handleRemoveComparedAsset}
          onClearAll={() => setComparedAssets([])}
        />
        ) : null}
      </aside>

      <section className="flex flex-1 bg-zinc-950">
        <MapView
          showPlants={showPlants}
          showSubstations={showSubstations}
          showLines={showLines}
          showGasPipelines={showGasPipelines}
          showGasImportPoints={showGasImports}
          showHydrogenPipelines={showHydrogenPipelines}
          showHydrogenProjects={showHydrogenProjects}
          showNatura2000={showNatura2000}
          showCells={showCells}
          plantsData={plantsData}
          substationsData={filteredSubstationsData}
          linesData={filteredLinesData}
          gasPipelinesData={gasPipelinesData}
          gasImportPointsData={gasImportPointsData}
          hydrogenPipelinesData={hydrogenPipelinesData}
          hydrogenProjectsData={hydrogenProjectsData}
          natura2000Data={natura2000Data}
          filteredCellsData={filteredCellsData}
          selectedAsset={visibleSelectedAsset}
          focusRequest={focusRequest}
          highlightMarketSignal={marketHighlightEnabled}
          marketFlowDirection={marketFlowDirection}
          marketSummary={marketSignal?.summary ?? null}
          marketPriceEurMwh={marketSignal?.currentPrice.valueEurMwh ?? null}
          marketZoneData={marketZoneData}
          showGeneratorClusters={showGeneratorClusters}
          generatorClustersData={generatorClustersData}
          showScenarioRegions={showScenarioRegions}
          scenarioRegionsData={scenarioRegionsData}
          onViewportChange={setViewportBounds}
          onSelectAsset={setSelectedAsset}
          onClearSelection={() => setSelectedAsset(null)}
        />

        {visibleSelectedAsset ? (
          <AssetDetailsDrawer
            asset={visibleSelectedAsset}
            onClose={() => setSelectedAsset(null)}
            isCompared={comparedAssets.some(
              (asset) => asset.id === visibleSelectedAsset.id,
            )}
            compareLimitReached={comparedAssets.length >= 3}
            onAddToCompare={handleAddComparedAsset}
            onRemoveFromCompare={handleRemoveComparedAsset}
          />
        ) : null}
      </section>
    </main>
  );

  function handleAssetFocus(asset: AssetSelection) {
    if (asset.assetType === "cell" && viewMode === "explorer") {
      handleViewModeChange("analysis");
    }

    setSelectedAsset(asset);
    setFocusRequest({
      asset,
      timestamp: Date.now(),
    });
    setSearchQuery("");
  }

  function handleViewModeChange(nextMode: ViewMode) {
    setViewMode(nextMode);

    if (nextMode === "explorer") {
      setShowCells(false);

      if (selectedAsset?.assetType === "cell") {
        setSelectedAsset(null);
      }

      return;
    }

    setShowCells(true);
  }

  function togglePlantTechnology(category: PlantTechnologyCategory) {
    setEnabledPlantTechnologies((current) => {
      if (current.includes(category)) {
        const nextSelection = current.filter((item) => item !== category);
        return nextSelection.length > 0 ? nextSelection : current;
      }

      return [...current, category];
    });
  }

  function togglePlantStatus(status: PlantStatusCategory) {
    setEnabledPlantStatuses((current) => {
      if (current.includes(status)) {
        const nextSelection = current.filter((item) => item !== status);
        return nextSelection.length > 0 ? nextSelection : current;
      }

      return [...current, status];
    });
  }

  function handleExcludeNatura2000Change(checked: boolean) {
    setExcludeNatura2000(checked);

    if (checked) {
      setShowNatura2000(true);
    }
  }

  function handleAddComparedAsset(asset: AssetSelection) {
    if (asset.assetType !== "cell") {
      return;
    }

    setComparedAssets((current) => {
      if (current.some((item) => item.id === asset.id)) {
        return current;
      }

      if (current.length >= 3) {
        return current;
      }

      return [...current, asset];
    });
  }

  function handleRemoveComparedAsset(assetId: string) {
    setComparedAssets((current) =>
      current.filter((asset) => asset.id !== assetId),
    );
  }

  async function loadCandidateCells() {
    setCandidateLoadState("loading");
    setCandidateLoadErrorMessage("");

    try {
      const response = await fetch(CANDIDATES_API_URL);

      if (!response.ok) {
        setCandidateLoadState("error");
        setCandidateLoadErrorMessage(
          "Could not load candidate cells from backend.",
        );
        return;
      }

      const featureCollection =
        (await response.json()) as GeoJSON.FeatureCollection;

      setCandidateCellAssets(buildSelections(featureCollection, "cell"));
      setCandidateLoadState("success");
    } catch {
      setCandidateLoadState("error");
      setCandidateLoadErrorMessage(
        "Backend unavailable for candidate cell loading.",
      );
    }
  }

  async function loadPilotInfrastructure() {
    setInfrastructureLoadState("loading");
    setInfrastructureLoadErrorMessage("");

    try {
      const [
        plantsFeatureCollection,
        substationsFeatureCollection,
        linesFeatureCollection,
        gasPipelinesFeatureCollection,
        gasImportPointsFeatureCollection,
        hydrogenPipelinesFeatureCollection,
        hydrogenProjectsFeatureCollection,
        natura2000FeatureCollection,
      ] =
        (await Promise.all([
          loadGeoJsonLayerWithRetry(PLANTS_API_URL, "Power plants"),
          loadGeoJsonLayerWithRetry(SUBSTATIONS_API_URL, "Substations"),
          loadGeoJsonLayerWithRetry(
            TRANSMISSION_LINES_API_URL,
            "Transmission lines",
          ),
          loadGeoJsonLayerWithRetry(GAS_PIPELINES_API_URL, "Gas pipelines"),
          loadGeoJsonLayerWithRetry(
            GAS_IMPORT_POINTS_API_URL,
            "Gas import points",
          ),
          loadGeoJsonLayerWithRetry(
            HYDROGEN_PIPELINES_API_URL,
            "Hydrogen pipelines",
          ),
          loadGeoJsonLayerWithRetry(
            HYDROGEN_PROJECTS_API_URL,
            "Hydrogen projects",
          ),
          loadGeoJsonLayerWithRetry(NATURA_2000_API_URL, "Natura 2000"),
        ])) as [
          GeoJSON.FeatureCollection,
          GeoJSON.FeatureCollection,
          GeoJSON.FeatureCollection,
          GeoJSON.FeatureCollection,
          GeoJSON.FeatureCollection,
          GeoJSON.FeatureCollection,
          GeoJSON.FeatureCollection,
          GeoJSON.FeatureCollection,
        ];

      setAllPlantAssets(
        buildSelections(plantsFeatureCollection, "plant").filter(
          (asset) => isDisplayablePlantAsset(asset),
        ),
      );
      setSubstationAssets(buildSelections(substationsFeatureCollection, "substation"));
      setLineAssets(buildSelections(linesFeatureCollection, "line"));
      setGasPipelineAssets(
        buildSelections(
          alignGasPipelineRoutes(
            gasPipelinesFeatureCollection,
            hydrogenPipelinesFeatureCollection,
          ),
          "gasPipeline",
        ),
      );
      setGasImportPointAssets(
        buildSelections(gasImportPointsFeatureCollection, "gasImportPoint"),
      );
      setHydrogenPipelineAssets(
        buildSelections(hydrogenPipelinesFeatureCollection, "hydrogenPipeline"),
      );
      setHydrogenProjectAssets(
        buildSelections(hydrogenProjectsFeatureCollection, "hydrogenProject"),
      );
      setNatura2000Data(natura2000FeatureCollection);
      setInfrastructureLoadState("success");
    } catch (error) {
      setInfrastructureLoadState("error");
      setInfrastructureLoadErrorMessage(
        error instanceof Error
          ? error.message
          : "Could not load Greece-wide infrastructure from backend.",
      );
    }
  }

  async function loadAssetClimate(
    asset: AssetSelection,
    coordinates: [number, number],
    signal: AbortSignal,
  ) {
    setClimateRequestState("loading");
    setClimateErrorMessage("");

    const [longitude, latitude] = coordinates;
    const query = new URLSearchParams({
      latitude: String(latitude),
      longitude: String(longitude),
      technology: String(asset.properties.technology ?? "Unknown"),
    });

    try {
      const response = await fetch(`${CLIMATE_ASSET_API_URL}?${query.toString()}`, {
        signal,
      });

      if (!response.ok) {
        setClimateRequestState("error");
        setClimateErrorMessage(
          "Climate data request failed. Backend unavailable or returned an error.",
        );
        return;
      }

      const payload = (await response.json()) as ClimateAssetResponse;
      setAssetClimate(payload);
      setClimateRequestState("success");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }

      setClimateRequestState("error");
      setClimateErrorMessage("Could not reach climate data service.");
    }
  }

  async function loadMarketSignal() {
    setMarketRequestState("loading");
    setMarketErrorMessage("");

    try {
      const response = await fetch(MARKET_GREECE_API_URL);

      if (!response.ok) {
        setMarketRequestState("error");
        setMarketErrorMessage(
          "Market signal request failed. Backend unavailable or returned an error.",
        );
        return;
      }

      const payload = (await response.json()) as GreeceMarketSignalResponse;
      setMarketSignal(payload);

      if (payload.status === "error") {
        setMarketRequestState("error");
        setMarketErrorMessage(payload.summary);
        return;
      }

      setMarketRequestState("success");
    } catch {
      setMarketRequestState("error");
      setMarketErrorMessage("Could not reach market signal service.");
    }
  }

  async function loadMarketZoneBoundary() {
    try {
      const featureCollection = await loadGeoJsonLayer(
        MARKET_GREECE_BOUNDARY_API_URL,
        "Greece market boundary",
      );
      setMarketZoneData(featureCollection);
    } catch {
      setMarketZoneData(emptyFeatureCollection);
    }
  }

  async function loadGeneratorClusters() {
    try {
      const featureCollection = await getGeneratorClustersGeoJson();
      setGeneratorClustersData(featureCollection);
    } catch {
      // Real asset clusters are a "nice to have" reference layer, not core
      // to any other panel -- fail silently (empty layer) rather than
      // surfacing a load error for a layer the user may never enable.
      setGeneratorClustersData(emptyFeatureCollection);
    }
  }

  async function loadScenarioRegions(caseName: string) {
    try {
      const featureCollection = await getScenarioRegionsGeoJson(caseName);
      setScenarioRegionsData(featureCollection);
    } catch {
      setScenarioRegionsData(emptyFeatureCollection);
    }
  }
}

async function loadGeoJsonLayerWithRetry(
  url: string,
  layerName: string,
): Promise<GeoJSON.FeatureCollection> {
  try {
    return await loadGeoJsonLayer(url, layerName);
  } catch {
    // A short retry helps when the backend is still starting up locally.
    await wait(500);
    return loadGeoJsonLayer(url, layerName);
  }
}

async function loadGeoJsonLayer(
  url: string,
  layerName: string,
): Promise<GeoJSON.FeatureCollection> {
  let response: Response;

  try {
    response = await fetch(url);
  } catch {
    throw new Error(`${layerName} backend unavailable.`);
  }

  if (!response.ok) {
    throw new Error(
      `${layerName} endpoint failed (${response.status} ${response.statusText}).`,
    );
  }

  const payload = (await response.json()) as Partial<GeoJSON.FeatureCollection>;

  if (payload.type !== "FeatureCollection" || !Array.isArray(payload.features)) {
    throw new Error(`${layerName} endpoint returned invalid GeoJSON.`);
  }

  return payload as GeoJSON.FeatureCollection;
}

function wait(milliseconds: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function getPointCoordinates(asset: AssetSelection | null) {
  if (!asset || asset.feature.geometry.type !== "Point") {
    return null;
  }

  return asset.feature.geometry.coordinates as [number, number];
}

function getVisibleSelectedAsset(
  selectedAsset: AssetSelection | null,
  visibility: {
    viewMode: ViewMode;
    showPlants: boolean;
    showSubstations: boolean;
    showLines: boolean;
    showGasPipelines: boolean;
    showGasImports: boolean;
    showHydrogenPipelines: boolean;
    showHydrogenProjects: boolean;
    showNatura2000: boolean;
    showCells: boolean;
    enabledPlantTechnologies: PlantTechnologyCategory[];
    enabledPlantStatuses: PlantStatusCategory[];
    voltageFilter: string;
    scenario: Scenario;
    excludeNatura2000: boolean;
    natura2000Data: GeoJSON.FeatureCollection;
  },
) {
  if (!selectedAsset) {
    return null;
  }

  if (selectedAsset.assetType === "plant" && !visibility.showPlants) {
    return null;
  }

  if (
    selectedAsset.assetType === "plant" &&
    !matchesPlantTechnology(selectedAsset, visibility.enabledPlantTechnologies)
  ) {
    return null;
  }

  if (
    selectedAsset.assetType === "plant" &&
    !matchesPlantStatus(selectedAsset, visibility.enabledPlantStatuses)
  ) {
    return null;
  }

  if (selectedAsset.assetType === "substation" && !visibility.showSubstations) {
    return null;
  }

  if (
    selectedAsset.assetType === "substation" &&
    !matchesVoltageFilter(selectedAsset, visibility.voltageFilter)
  ) {
    return null;
  }

  if (selectedAsset.assetType === "line" && !visibility.showLines) {
    return null;
  }

  if (
    selectedAsset.assetType === "line" &&
    !matchesVoltageFilter(selectedAsset, visibility.voltageFilter)
  ) {
    return null;
  }

  if (selectedAsset.assetType === "gasPipeline" && !visibility.showGasPipelines) {
    return null;
  }

  if (
    selectedAsset.assetType === "gasImportPoint" &&
    !visibility.showGasImports
  ) {
    return null;
  }

  if (
    selectedAsset.assetType === "hydrogenPipeline" &&
    !visibility.showHydrogenPipelines
  ) {
    return null;
  }

  if (
    selectedAsset.assetType === "hydrogenProject" &&
    !visibility.showHydrogenProjects
  ) {
    return null;
  }

  if (
    selectedAsset.assetType === "cell" &&
    (!visibility.showCells ||
      !matchesCandidateScenario(selectedAsset, visibility.scenario) ||
      isCandidateExcludedByNatura(
        selectedAsset,
        visibility.natura2000Data,
        visibility.excludeNatura2000,
      ))
  ) {
    return null;
  }

  return selectedAsset;
}

function getTopOpportunities(assets: AssetSelection[]) {
  return sortCandidatesByInvestmentScore(assets).slice(0, 5);
}

function getMarketFlowDirection(
  marketSignal: GreeceMarketSignalResponse | null,
): MarketFlowDirection {
  if (!marketSignal || marketSignal.status !== "success") {
    return "unavailable";
  }

  if (marketSignal.netImportMw > 0) {
    return "import";
  }

  if (marketSignal.netImportMw < 0) {
    return "export";
  }

  return "balanced";
}
