"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import type {
  CircleLayerSpecification,
  ExpressionSpecification,
  LineLayerSpecification,
} from "maplibre-gl";
import type {
  AssetSelection,
  AssetType,
  FocusRequest,
  ViewportBounds,
} from "../types/asset";
import type { MarketFlowDirection } from "../types/market";

type MapViewProps = {
  showPlants: boolean;
  showSubstations: boolean;
  showLines: boolean;
  showGasPipelines: boolean;
  showGasImportPoints: boolean;
  showHydrogenPipelines: boolean;
  showHydrogenProjects: boolean;
  showNatura2000: boolean;
  showCells: boolean;
  plantsData: GeoJSON.FeatureCollection;
  substationsData: GeoJSON.FeatureCollection;
  linesData: GeoJSON.FeatureCollection;
  gasPipelinesData: GeoJSON.FeatureCollection;
  gasImportPointsData: GeoJSON.FeatureCollection;
  hydrogenPipelinesData: GeoJSON.FeatureCollection;
  hydrogenProjectsData: GeoJSON.FeatureCollection;
  natura2000Data: GeoJSON.FeatureCollection;
  filteredCellsData: GeoJSON.FeatureCollection;
  selectedAsset: AssetSelection | null;
  focusRequest: FocusRequest | null;
  highlightMarketSignal: boolean;
  marketFlowDirection: MarketFlowDirection;
  marketSummary: string | null;
  marketPriceEurMwh: number | null;
  marketZoneData: GeoJSON.FeatureCollection;
  showGeneratorClusters: boolean;
  generatorClustersData: GeoJSON.FeatureCollection;
  showScenarioRegions: boolean;
  scenarioRegionsData: GeoJSON.FeatureCollection;
  onViewportChange: (bounds: ViewportBounds) => void;
  onSelectAsset: (asset: AssetSelection) => void;
  onClearSelection: () => void;
};

const GREECE_CENTER: [number, number] = [22.0, 39.0];
const INITIAL_ZOOM = 5.5;

const PLANTS_SOURCE_ID = "plants-source";
const SUBSTATIONS_SOURCE_ID = "substations-source";
const LINES_SOURCE_ID = "lines-source";
const GAS_PIPELINES_SOURCE_ID = "gas-pipelines-source";
const GAS_IMPORT_POINTS_SOURCE_ID = "gas-import-points-source";
const HYDROGEN_PIPELINES_SOURCE_ID = "hydrogen-pipelines-source";
const HYDROGEN_PROJECTS_SOURCE_ID = "hydrogen-projects-source";
const NATURA_2000_SOURCE_ID = "natura-2000-source";
const CELLS_SOURCE_ID = "cells-source";
const SELECTED_SOURCE_ID = "selected-asset-source";
const MARKET_ZONE_SOURCE_ID = "market-zone-source";
const GENERATOR_CLUSTERS_SOURCE_ID = "generator-clusters-source";
const SCENARIO_REGIONS_SOURCE_ID = "scenario-regions-source";

const PLANTS_LAYER_ID = "plants-layer";
const SUBSTATIONS_LAYER_ID = "substations-layer";
const LINES_LAYER_ID = "lines-layer";
const GAS_PIPELINES_LAYER_ID = "gas-pipelines-layer";
const GAS_PIPELINES_CASING_LAYER_ID = "gas-pipelines-casing-layer";
const GAS_IMPORT_POINTS_LAYER_ID = "gas-import-points-layer";
const GAS_IMPORT_LABEL_LAYER_ID = "gas-import-label-layer";
const HYDROGEN_PIPELINES_CASING_LAYER_ID = "hydrogen-pipelines-casing-layer";
const HYDROGEN_PIPELINES_LAYER_ID = "hydrogen-pipelines-layer";
const HYDROGEN_PROJECTS_LAYER_ID = "hydrogen-projects-layer";
const NATURA_2000_FILL_LAYER_ID = "natura-2000-fill-layer";
const NATURA_2000_OUTLINE_LAYER_ID = "natura-2000-outline-layer";
const CELLS_LAYER_ID = "cells-layer";
const MARKET_ZONE_FILL_LAYER_ID = "market-zone-fill-layer";
const MARKET_ZONE_OUTLINE_LAYER_ID = "market-zone-outline-layer";
const MARKET_ZONE_LABEL_LAYER_ID = "market-zone-label-layer";
const GENERATOR_CLUSTERS_CLUSTERS_LAYER_ID = "generator-clusters-clusters-layer";
const GENERATOR_CLUSTERS_CLUSTER_COUNT_LAYER_ID = "generator-clusters-cluster-count-layer";
const GENERATOR_CLUSTERS_POINT_LAYER_ID = "generator-clusters-point-layer";
const SCENARIO_REGIONS_FILL_LAYER_ID = "scenario-regions-fill-layer";
const SCENARIO_REGIONS_OUTLINE_LAYER_ID = "scenario-regions-outline-layer";
const PLANTS_CLUSTERS_LAYER_ID = "plants-clusters-layer";
const PLANTS_CLUSTER_COUNT_LAYER_ID = "plants-cluster-count-layer";
const SUBSTATIONS_CLUSTERS_LAYER_ID = "substations-clusters-layer";
const SUBSTATIONS_CLUSTER_COUNT_LAYER_ID = "substations-cluster-count-layer";
const SELECTED_POINTS_LAYER_ID = "selected-points-layer";
const SELECTED_LINES_LAYER_ID = "selected-lines-layer";
const SELECTED_POLYGONS_LAYER_ID = "selected-polygons-layer";
const SELECTED_POLYGON_OUTLINE_LAYER_ID = "selected-polygon-outline-layer";

const CLICKABLE_LAYER_IDS = [
  PLANTS_LAYER_ID,
  SUBSTATIONS_LAYER_ID,
  LINES_LAYER_ID,
  GAS_PIPELINES_LAYER_ID,
  GAS_IMPORT_POINTS_LAYER_ID,
  HYDROGEN_PIPELINES_LAYER_ID,
  HYDROGEN_PROJECTS_LAYER_ID,
  CELLS_LAYER_ID,
] as const;

const CLUSTER_LAYER_IDS = [
  PLANTS_CLUSTERS_LAYER_ID,
  SUBSTATIONS_CLUSTERS_LAYER_ID,
] as const;

const emptySelection = {
  type: "FeatureCollection" as const,
  features: [],
};

export default function MapView({
  showPlants,
  showSubstations,
  showLines,
  showGasPipelines,
  showGasImportPoints,
  showHydrogenPipelines,
  showHydrogenProjects,
  showNatura2000,
  showCells,
  plantsData,
  substationsData,
  linesData,
  gasPipelinesData,
  gasImportPointsData,
  hydrogenPipelinesData,
  hydrogenProjectsData,
  natura2000Data,
  filteredCellsData,
  selectedAsset,
  focusRequest,
  highlightMarketSignal,
  marketFlowDirection,
  marketSummary,
  marketPriceEurMwh,
  marketZoneData,
  showGeneratorClusters,
  generatorClustersData,
  showScenarioRegions,
  scenarioRegionsData,
  onViewportChange,
  onSelectAsset,
  onClearSelection,
}: MapViewProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const isMapLoadedRef = useRef(false);
  const showPlantsRef = useRef(showPlants);
  const showSubstationsRef = useRef(showSubstations);
  const showLinesRef = useRef(showLines);
  const showGasPipelinesRef = useRef(showGasPipelines);
  const showGasImportPointsRef = useRef(showGasImportPoints);
  const showHydrogenPipelinesRef = useRef(showHydrogenPipelines);
  const showHydrogenProjectsRef = useRef(showHydrogenProjects);
  const showNatura2000Ref = useRef(showNatura2000);
  const showCellsRef = useRef(showCells);
  const onViewportChangeRef = useRef(onViewportChange);
  const onSelectAssetRef = useRef(onSelectAsset);
  const onClearSelectionRef = useRef(onClearSelection);
  const selectedAssetRef = useRef(selectedAsset);
  const filteredCellsDataRef = useRef(filteredCellsData);
  const plantsDataRef = useRef(plantsData);
  const substationsDataRef = useRef(substationsData);
  const linesDataRef = useRef(linesData);
  const gasPipelinesDataRef = useRef(gasPipelinesData);
  const gasImportPointsDataRef = useRef(gasImportPointsData);
  const hydrogenPipelinesDataRef = useRef(hydrogenPipelinesData);
  const hydrogenProjectsDataRef = useRef(hydrogenProjectsData);
  const natura2000DataRef = useRef(natura2000Data);
  const highlightMarketSignalRef = useRef(highlightMarketSignal);
  const marketFlowDirectionRef = useRef(marketFlowDirection);
  const marketPriceEurMwhRef = useRef(marketPriceEurMwh);
  const marketZoneDataRef = useRef(marketZoneData);
  const showGeneratorClustersRef = useRef(showGeneratorClusters);
  const generatorClustersDataRef = useRef(generatorClustersData);
  const showScenarioRegionsRef = useRef(showScenarioRegions);
  const scenarioRegionsDataRef = useRef(scenarioRegionsData);

  useEffect(() => {
    showPlantsRef.current = showPlants;
  }, [showPlants]);

  useEffect(() => {
    showSubstationsRef.current = showSubstations;
  }, [showSubstations]);

  useEffect(() => {
    showLinesRef.current = showLines;
  }, [showLines]);

  useEffect(() => {
    showGasPipelinesRef.current = showGasPipelines;
  }, [showGasPipelines]);

  useEffect(() => {
    showGasImportPointsRef.current = showGasImportPoints;
  }, [showGasImportPoints]);

  useEffect(() => {
    showHydrogenPipelinesRef.current = showHydrogenPipelines;
  }, [showHydrogenPipelines]);

  useEffect(() => {
    showHydrogenProjectsRef.current = showHydrogenProjects;
  }, [showHydrogenProjects]);

  useEffect(() => {
    showNatura2000Ref.current = showNatura2000;
  }, [showNatura2000]);

  useEffect(() => {
    showCellsRef.current = showCells;
  }, [showCells]);

  useEffect(() => {
    onSelectAssetRef.current = onSelectAsset;
  }, [onSelectAsset]);

  useEffect(() => {
    onViewportChangeRef.current = onViewportChange;
  }, [onViewportChange]);

  useEffect(() => {
    onClearSelectionRef.current = onClearSelection;
  }, [onClearSelection]);

  useEffect(() => {
    selectedAssetRef.current = selectedAsset;
  }, [selectedAsset]);

  useEffect(() => {
    filteredCellsDataRef.current = filteredCellsData;
  }, [filteredCellsData]);

  useEffect(() => {
    plantsDataRef.current = plantsData;
  }, [plantsData]);

  useEffect(() => {
    substationsDataRef.current = substationsData;
  }, [substationsData]);

  useEffect(() => {
    linesDataRef.current = linesData;
  }, [linesData]);

  useEffect(() => {
    gasPipelinesDataRef.current = gasPipelinesData;
  }, [gasPipelinesData]);

  useEffect(() => {
    gasImportPointsDataRef.current = gasImportPointsData;
  }, [gasImportPointsData]);

  useEffect(() => {
    hydrogenPipelinesDataRef.current = hydrogenPipelinesData;
  }, [hydrogenPipelinesData]);

  useEffect(() => {
    hydrogenProjectsDataRef.current = hydrogenProjectsData;
  }, [hydrogenProjectsData]);

  useEffect(() => {
    natura2000DataRef.current = natura2000Data;
  }, [natura2000Data]);

  useEffect(() => {
    highlightMarketSignalRef.current = highlightMarketSignal;
  }, [highlightMarketSignal]);

  useEffect(() => {
    marketFlowDirectionRef.current = marketFlowDirection;
  }, [marketFlowDirection]);

  useEffect(() => {
    marketPriceEurMwhRef.current = marketPriceEurMwh;
  }, [marketPriceEurMwh]);

  useEffect(() => {
    marketZoneDataRef.current = marketZoneData;
  }, [marketZoneData]);

  useEffect(() => {
    showGeneratorClustersRef.current = showGeneratorClusters;
  }, [showGeneratorClusters]);

  useEffect(() => {
    generatorClustersDataRef.current = generatorClustersData;
  }, [generatorClustersData]);

  useEffect(() => {
    showScenarioRegionsRef.current = showScenarioRegions;
  }, [showScenarioRegions]);

  useEffect(() => {
    scenarioRegionsDataRef.current = scenarioRegionsData;
  }, [scenarioRegionsData]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) {
      return;
    }

    // Set on cleanup so handlers of a map that is being torn down (queued
    // behind a still-loading style) do nothing.
    let isDisposed = false;

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
      center: GREECE_CENTER,
      zoom: INITIAL_ZOOM,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    // Wait for the style load event before adding sources and layers.
    // Until the style is ready, layer and source operations can fail.
    map.on("load", () => {
      if (isDisposed) {
        return;
      }

      isMapLoadedRef.current = true;

      addMarketZoneLayers(
        map,
        buildMarketZoneData(marketPriceEurMwhRef.current, marketZoneDataRef.current),
        highlightMarketSignalRef.current,
      );

      addLayerGroup(map, CELLS_SOURCE_ID, filteredCellsDataRef.current, {
        id: CELLS_LAYER_ID,
        type: "fill",
        source: CELLS_SOURCE_ID,
        layout: {
          visibility: showCellsRef.current ? "visible" : "none",
        },
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "investment_score"],
            40,
            "#7f1d1d",
            55,
            "#b45309",
            70,
            "#ca8a04",
            85,
            "#15803d",
          ],
          "fill-opacity": 0.32,
          "fill-outline-color": [
            "case",
            ["==", ["get", "land_excluded"], true],
            "#f8fafc",
            "#d4d4d8",
          ],
        },
      });

      addLayerGroup(map, NATURA_2000_SOURCE_ID, natura2000DataRef.current, {
        id: NATURA_2000_FILL_LAYER_ID,
        type: "fill",
        source: NATURA_2000_SOURCE_ID,
        layout: {
          visibility: showNatura2000Ref.current ? "visible" : "none",
        },
        paint: {
          "fill-color": "#22c55e",
          "fill-opacity": 0.16,
        },
      });

      addLayerGroup(map, NATURA_2000_SOURCE_ID, natura2000DataRef.current, {
        id: NATURA_2000_OUTLINE_LAYER_ID,
        type: "line",
        source: NATURA_2000_SOURCE_ID,
        layout: {
          visibility: showNatura2000Ref.current ? "visible" : "none",
        },
        paint: {
          "line-color": "#4ade80",
          "line-opacity": 0.85,
          "line-width": 1.3,
        },
      });

      addLayerGroup(map, LINES_SOURCE_ID, linesDataRef.current, {
        id: LINES_LAYER_ID,
        type: "line",
        source: LINES_SOURCE_ID,
        layout: {
          visibility: showLinesRef.current ? "visible" : "none",
          "line-cap": "round",
          "line-join": "round",
        },
        paint: getTransmissionLinePaint(false),
      });

      addClusteredPointLayers(map, {
        sourceId: PLANTS_SOURCE_ID,
        data: plantsDataRef.current,
        clusterLayerId: PLANTS_CLUSTERS_LAYER_ID,
        clusterCountLayerId: PLANTS_CLUSTER_COUNT_LAYER_ID,
        pointLayerId: PLANTS_LAYER_ID,
        pointColor: getPlantTechnologyColorExpression(),
        pointStrokeColor: "#052e16",
        clusterColor: "#059669",
        isVisible: showPlantsRef.current,
      });

      addClusteredPointLayers(map, {
        sourceId: SUBSTATIONS_SOURCE_ID,
        data: substationsDataRef.current,
        clusterLayerId: SUBSTATIONS_CLUSTERS_LAYER_ID,
        clusterCountLayerId: SUBSTATIONS_CLUSTER_COUNT_LAYER_ID,
        pointLayerId: SUBSTATIONS_LAYER_ID,
        pointColor: "#fb7185",
        pointStrokeColor: "#4c0519",
        clusterColor: "#e11d48",
        isVisible: showSubstationsRef.current,
      });

      addLayerGroup(map, GAS_PIPELINES_SOURCE_ID, gasPipelinesDataRef.current, {
        id: GAS_PIPELINES_CASING_LAYER_ID,
        type: "line",
        source: GAS_PIPELINES_SOURCE_ID,
        layout: {
          visibility: showGasPipelinesRef.current ? "visible" : "none",
          "line-cap": "round",
          "line-join": "round",
        },
        paint: getGasPipelineCasingPaint(),
      });

      addLayerGroup(map, GAS_PIPELINES_SOURCE_ID, gasPipelinesDataRef.current, {
        id: GAS_PIPELINES_LAYER_ID,
        type: "line",
        source: GAS_PIPELINES_SOURCE_ID,
        layout: {
          visibility: showGasPipelinesRef.current ? "visible" : "none",
          "line-cap": "round",
          "line-join": "round",
        },
        paint: getGasPipelinePaint(),
      });

      addLayerGroup(map, GAS_IMPORT_POINTS_SOURCE_ID, gasImportPointsDataRef.current, {
        id: GAS_IMPORT_POINTS_LAYER_ID,
        type: "circle",
        source: GAS_IMPORT_POINTS_SOURCE_ID,
        layout: {
          visibility: showGasImportPointsRef.current ? "visible" : "none",
        },
        paint: getGasImportPointPaint(),
      });

      addLayerGroup(map, GAS_IMPORT_POINTS_SOURCE_ID, gasImportPointsDataRef.current, {
        id: GAS_IMPORT_LABEL_LAYER_ID,
        type: "symbol",
        source: GAS_IMPORT_POINTS_SOURCE_ID,
        layout: {
          visibility: showGasImportPointsRef.current ? "visible" : "none",
          "text-field": ["get", "name"],
          "text-font": ["Open Sans Semibold"],
          "text-size": 11,
          "text-offset": [0, 1.3],
          "text-anchor": "top",
          "text-allow-overlap": false,
        },
        paint: {
          "text-color": "#fde68a",
          "text-halo-color": "#111827",
          "text-halo-width": 1.5,
          "text-opacity": 0.92,
        },
      });

      addLayerGroup(map, HYDROGEN_PIPELINES_SOURCE_ID, hydrogenPipelinesDataRef.current, {
        id: HYDROGEN_PIPELINES_CASING_LAYER_ID,
        type: "line",
        source: HYDROGEN_PIPELINES_SOURCE_ID,
        layout: {
          visibility: showHydrogenPipelinesRef.current ? "visible" : "none",
          "line-cap": "round",
          "line-join": "round",
        },
        paint: getHydrogenPipelineCasingPaint(),
      });

      addLayerGroup(map, HYDROGEN_PIPELINES_SOURCE_ID, hydrogenPipelinesDataRef.current, {
        id: HYDROGEN_PIPELINES_LAYER_ID,
        type: "line",
        source: HYDROGEN_PIPELINES_SOURCE_ID,
        layout: {
          visibility: showHydrogenPipelinesRef.current ? "visible" : "none",
          "line-cap": "round",
          "line-join": "round",
        },
        paint: getHydrogenPipelinePaint(),
      });

      addLayerGroup(map, HYDROGEN_PROJECTS_SOURCE_ID, hydrogenProjectsDataRef.current, {
        id: HYDROGEN_PROJECTS_LAYER_ID,
        type: "circle",
        source: HYDROGEN_PROJECTS_SOURCE_ID,
        layout: {
          visibility: showHydrogenProjectsRef.current ? "visible" : "none",
        },
        paint: getHydrogenProjectPaint(),
      });

      addClusteredPointLayers(map, {
        sourceId: GENERATOR_CLUSTERS_SOURCE_ID,
        data: generatorClustersDataRef.current,
        clusterLayerId: GENERATOR_CLUSTERS_CLUSTERS_LAYER_ID,
        clusterCountLayerId: GENERATOR_CLUSTERS_CLUSTER_COUNT_LAYER_ID,
        pointLayerId: GENERATOR_CLUSTERS_POINT_LAYER_ID,
        pointColor: "#c084fc",
        pointStrokeColor: "#3b0764",
        clusterColor: "#a855f7",
        isVisible: showGeneratorClustersRef.current,
      });

      // Scenario-solve results (real, per-region metrics from a solved PyPSA
      // scenario) -- empty FeatureCollection until a scenario is solved, see
      // addScenarioRegionLayers below.
      addScenarioRegionLayers(map, scenarioRegionsDataRef.current, showScenarioRegionsRef.current);

      addSelectedLayers(map);
      bringLayerInFront(map, GAS_PIPELINES_CASING_LAYER_ID, SELECTED_POLYGONS_LAYER_ID);
      bringLayerInFront(map, GAS_PIPELINES_LAYER_ID, SELECTED_POLYGONS_LAYER_ID);
      bringLayerInFront(map, GAS_IMPORT_POINTS_LAYER_ID, SELECTED_POLYGONS_LAYER_ID);
      bringLayerInFront(map, GAS_IMPORT_LABEL_LAYER_ID, SELECTED_POLYGONS_LAYER_ID);
      bringLayerInFront(map, HYDROGEN_PIPELINES_CASING_LAYER_ID, SELECTED_POLYGONS_LAYER_ID);
      bringLayerInFront(map, HYDROGEN_PIPELINES_LAYER_ID, SELECTED_POLYGONS_LAYER_ID);
      bringLayerInFront(map, HYDROGEN_PROJECTS_LAYER_ID, SELECTED_POLYGONS_LAYER_ID);

      map.on("click", PLANTS_CLUSTERS_LAYER_ID, (event) => {
        zoomToCluster(map, event, PLANTS_CLUSTERS_LAYER_ID, PLANTS_SOURCE_ID);
      });

      map.on("click", SUBSTATIONS_CLUSTERS_LAYER_ID, (event) => {
        zoomToCluster(
          map,
          event,
          SUBSTATIONS_CLUSTERS_LAYER_ID,
          SUBSTATIONS_SOURCE_ID,
        );
      });

      map.on("click", (event) => {
        const features = map.queryRenderedFeatures(event.point, {
          layers: [...CLICKABLE_LAYER_IDS],
        });

        const feature = pickFeatureAtClick(features);
        if (!feature) {
          onClearSelectionRef.current();
          return;
        }

        const selected = createAssetSelection(feature);
        if (selected) {
          onSelectAssetRef.current(selected);
        }
      });

      for (const layerId of [...CLUSTER_LAYER_IDS, ...CLICKABLE_LAYER_IDS]) {
        map.on("mouseenter", layerId, () => {
          map.getCanvas().style.cursor = "pointer";
        });

        map.on("mouseleave", layerId, () => {
          map.getCanvas().style.cursor = "";
        });
      }

      updateLayerGroupVisibility(
        map,
        true,
        [PLANTS_CLUSTERS_LAYER_ID, PLANTS_CLUSTER_COUNT_LAYER_ID, PLANTS_LAYER_ID],
        showPlantsRef.current,
      );
      updateLayerGroupVisibility(
        map,
        true,
        [
          SUBSTATIONS_CLUSTERS_LAYER_ID,
          SUBSTATIONS_CLUSTER_COUNT_LAYER_ID,
          SUBSTATIONS_LAYER_ID,
        ],
        showSubstationsRef.current,
      );
      updateLayerVisibility(map, true, LINES_LAYER_ID, showLinesRef.current);
      updateLayerVisibility(
        map,
        true,
        GAS_PIPELINES_CASING_LAYER_ID,
        showGasPipelinesRef.current,
      );
      updateLayerVisibility(
        map,
        true,
        GAS_PIPELINES_LAYER_ID,
        showGasPipelinesRef.current,
      );
      updateLayerVisibility(
        map,
        true,
        GAS_IMPORT_POINTS_LAYER_ID,
        showGasImportPointsRef.current,
      );
      updateLayerVisibility(
        map,
        true,
        GAS_IMPORT_LABEL_LAYER_ID,
        showGasImportPointsRef.current,
      );
      updateLayerVisibility(
        map,
        true,
        HYDROGEN_PIPELINES_CASING_LAYER_ID,
        showHydrogenPipelinesRef.current,
      );
      updateLayerVisibility(
        map,
        true,
        HYDROGEN_PIPELINES_LAYER_ID,
        showHydrogenPipelinesRef.current,
      );
      updateLayerVisibility(
        map,
        true,
        HYDROGEN_PROJECTS_LAYER_ID,
        showHydrogenProjectsRef.current,
      );
      updateLayerVisibility(
        map,
        true,
        NATURA_2000_FILL_LAYER_ID,
        showNatura2000Ref.current,
      );
      updateLayerVisibility(
        map,
        true,
        NATURA_2000_OUTLINE_LAYER_ID,
        showNatura2000Ref.current,
      );
      updateLayerVisibility(map, true, CELLS_LAYER_ID, showCellsRef.current);
      updateMarketZoneStyle(
        map,
        true,
        highlightMarketSignalRef.current,
        marketPriceEurMwhRef.current,
        marketZoneDataRef.current,
      );
      updateSelectedFeature(map, selectedAssetRef.current);
      onViewportChangeRef.current(getViewportBounds(map));
    });

    map.on("moveend", () => {
      if (isDisposed) {
        return;
      }

      onViewportChangeRef.current(getViewportBounds(map));
    });

    return () => {
      isDisposed = true;
      mapRef.current = null;
      isMapLoadedRef.current = false;

      // MapLibre throws asynchronously ("Cannot read properties of undefined
      // (reading 'projection')") if remove() runs while the style JSON is
      // still loading. That happens whenever this component unmounts early:
      // a quick Map -> Studio route change, or React StrictMode's dev-only
      // mount/unmount/mount. So remove immediately only once the style is
      // ready; otherwise defer removal to the load event.
      if (map.isStyleLoaded()) {
        map.remove();
      } else {
        map.once("load", () => map.remove());
      }
    };
  }, []);

  useEffect(() => {
    updateLayerGroupVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      [PLANTS_CLUSTERS_LAYER_ID, PLANTS_CLUSTER_COUNT_LAYER_ID, PLANTS_LAYER_ID],
      showPlants,
    );
  }, [showPlants]);

  useEffect(() => {
    updateLayerGroupVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      [
        SUBSTATIONS_CLUSTERS_LAYER_ID,
        SUBSTATIONS_CLUSTER_COUNT_LAYER_ID,
        SUBSTATIONS_LAYER_ID,
      ],
      showSubstations,
    );
  }, [showSubstations]);

  useEffect(() => {
    updateLayerVisibility(mapRef.current, isMapLoadedRef.current, LINES_LAYER_ID, showLines);
  }, [showLines]);

  useEffect(() => {
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      GAS_PIPELINES_CASING_LAYER_ID,
      showGasPipelines,
    );
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      GAS_PIPELINES_LAYER_ID,
      showGasPipelines,
    );
  }, [showGasPipelines]);

  useEffect(() => {
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      GAS_IMPORT_POINTS_LAYER_ID,
      showGasImportPoints,
    );
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      GAS_IMPORT_LABEL_LAYER_ID,
      showGasImportPoints,
    );
  }, [showGasImportPoints]);


  useEffect(() => {
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      HYDROGEN_PIPELINES_CASING_LAYER_ID,
      showHydrogenPipelines,
    );
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      HYDROGEN_PIPELINES_LAYER_ID,
      showHydrogenPipelines,
    );
  }, [showHydrogenPipelines]);

  useEffect(() => {
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      HYDROGEN_PROJECTS_LAYER_ID,
      showHydrogenProjects,
    );
  }, [showHydrogenProjects]);

  useEffect(() => {
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      NATURA_2000_FILL_LAYER_ID,
      showNatura2000,
    );
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      NATURA_2000_OUTLINE_LAYER_ID,
      showNatura2000,
    );
  }, [showNatura2000]);

  useEffect(() => {
    updateLayerVisibility(mapRef.current, isMapLoadedRef.current, CELLS_LAYER_ID, showCells);
  }, [showCells]);

  useEffect(() => {
    updateLayerGroupVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      [
        GENERATOR_CLUSTERS_CLUSTERS_LAYER_ID,
        GENERATOR_CLUSTERS_CLUSTER_COUNT_LAYER_ID,
        GENERATOR_CLUSTERS_POINT_LAYER_ID,
      ],
      showGeneratorClusters,
    );
  }, [showGeneratorClusters]);

  useEffect(() => {
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      SCENARIO_REGIONS_FILL_LAYER_ID,
      showScenarioRegions,
    );
    updateLayerVisibility(
      mapRef.current,
      isMapLoadedRef.current,
      SCENARIO_REGIONS_OUTLINE_LAYER_ID,
      showScenarioRegions,
    );
  }, [showScenarioRegions]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      CELLS_SOURCE_ID,
      filteredCellsData,
    );
  }, [filteredCellsData]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      PLANTS_SOURCE_ID,
      plantsData,
    );
  }, [plantsData]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      GENERATOR_CLUSTERS_SOURCE_ID,
      generatorClustersData,
    );
  }, [generatorClustersData]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      SCENARIO_REGIONS_SOURCE_ID,
      scenarioRegionsData,
    );
  }, [scenarioRegionsData]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      SUBSTATIONS_SOURCE_ID,
      substationsData,
    );
  }, [substationsData]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      LINES_SOURCE_ID,
      linesData,
    );
  }, [linesData]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      GAS_PIPELINES_SOURCE_ID,
      gasPipelinesData,
    );
  }, [gasPipelinesData]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      GAS_IMPORT_POINTS_SOURCE_ID,
      gasImportPointsData,
    );
  }, [gasImportPointsData]);


  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      HYDROGEN_PIPELINES_SOURCE_ID,
      hydrogenPipelinesData,
    );
  }, [hydrogenPipelinesData]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      HYDROGEN_PROJECTS_SOURCE_ID,
      hydrogenProjectsData,
    );
  }, [hydrogenProjectsData]);

  useEffect(() => {
    updateGeoJsonSource(
      mapRef.current,
      isMapLoadedRef.current,
      NATURA_2000_SOURCE_ID,
      natura2000Data,
    );
  }, [natura2000Data]);

  useEffect(() => {
    updateSelectedFeature(mapRef.current, selectedAsset);
  }, [selectedAsset]);

  useEffect(() => {
    focusOnAsset(mapRef.current, isMapLoadedRef.current, focusRequest?.asset ?? null);
  }, [focusRequest]);

  useEffect(() => {
    updateMarketLineStyle(
      mapRef.current,
      isMapLoadedRef.current,
      highlightMarketSignal,
      marketFlowDirection,
    );
    updateMarketZoneStyle(
      mapRef.current,
      isMapLoadedRef.current,
      highlightMarketSignal,
      marketPriceEurMwh,
      marketZoneData,
    );
  }, [highlightMarketSignal, marketFlowDirection, marketPriceEurMwh, marketZoneData]);

  return (
    <div className="relative h-full w-full">
      <div ref={mapContainerRef} className="h-full w-full" />

      {highlightMarketSignal ? (
        <MarketMapOverlay
          direction={marketFlowDirection}
          price={marketPriceEurMwh}
          summary={marketSummary}
        />
      ) : null}
    </div>
  );
}

function MarketMapOverlay({
  direction,
  price,
  summary,
}: {
  direction: MarketFlowDirection;
  price: number | null;
  summary: string | null;
}) {
  return (
    <>
    <div className="pointer-events-none absolute left-6 top-6 max-w-sm rounded-2xl border border-white/10 bg-zinc-950/90 p-4 shadow-2xl shadow-black/40 backdrop-blur">
      <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-zinc-500">
        Electricity Price Signal
      </p>
      <div className="mt-3 flex items-center gap-3">
        <span
          className="h-3 w-3 rounded-full"
          style={{ backgroundColor: getMarketLineColor(direction) }}
        />
        <p className="text-sm font-semibold text-zinc-100">
          {getMarketDirectionLabel(direction)}
        </p>
      </div>
      <p className="mt-3 text-xs leading-5 text-zinc-300">
        {summary ??
          "Transmission lines are highlighted to show where market price and flow context will appear."}
      </p>
      <p className="mt-3 text-2xl font-semibold text-zinc-100">
        {formatMarketPrice(price)}
      </p>
      <div className="mt-4 grid grid-cols-3 gap-2 text-[10px] font-medium uppercase tracking-[0.16em]">
        <span className="rounded-full border border-sky-400/30 bg-sky-400/10 px-2 py-1 text-center text-sky-300">
          Import
        </span>
        <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-center text-amber-300">
          Export
        </span>
        <span className="rounded-full border border-zinc-400/30 bg-zinc-400/10 px-2 py-1 text-center text-zinc-300">
          Awaiting API
        </span>
      </div>
    </div>
    <div className="pointer-events-none absolute bottom-6 right-6 w-72 rounded-2xl border border-white/10 bg-zinc-950/90 p-4 shadow-2xl shadow-black/40 backdrop-blur">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-zinc-100">Electricity price</p>
        <p className="text-xs font-semibold text-zinc-300">€/MWh</p>
      </div>
      <div className="mt-3 h-2 rounded-full bg-gradient-to-r from-emerald-400 via-amber-300 via-rose-400 to-violet-600" />
      <div className="mt-2 flex justify-between text-xs text-zinc-400">
        <span>0</span>
        <span>80</span>
        <span>160</span>
        <span>240</span>
        <span>320</span>
        <span>400</span>
      </div>
    </div>
    </>
  );
}

function addMarketZoneLayers(
  map: maplibregl.Map,
  data: GeoJSON.FeatureCollection,
  isVisible: boolean,
) {
  if (!map.getSource(MARKET_ZONE_SOURCE_ID)) {
    map.addSource(MARKET_ZONE_SOURCE_ID, {
      type: "geojson",
      data,
    });
  }

  if (!map.getLayer(MARKET_ZONE_FILL_LAYER_ID)) {
    map.addLayer({
      id: MARKET_ZONE_FILL_LAYER_ID,
      type: "fill",
      source: MARKET_ZONE_SOURCE_ID,
      layout: {
        visibility: isVisible ? "visible" : "none",
      },
      paint: {
        "fill-color": getMarketPriceFillColorExpression(),
        "fill-opacity": 0.48,
      },
    });
  }

  if (!map.getLayer(MARKET_ZONE_OUTLINE_LAYER_ID)) {
    map.addLayer({
      id: MARKET_ZONE_OUTLINE_LAYER_ID,
      type: "line",
      source: MARKET_ZONE_SOURCE_ID,
      layout: {
        visibility: isVisible ? "visible" : "none",
      },
      paint: {
        "line-color": "#f8fafc",
        "line-opacity": 0.85,
        "line-width": 2.4,
      },
    });
  }

  if (!map.getLayer(MARKET_ZONE_LABEL_LAYER_ID)) {
    map.addLayer({
      id: MARKET_ZONE_LABEL_LAYER_ID,
      type: "symbol",
      source: MARKET_ZONE_SOURCE_ID,
      layout: {
        visibility: isVisible ? "visible" : "none",
        "text-field": ["get", "price_label"],
        "text-font": ["Open Sans Semibold"],
        "text-size": 16,
        "text-offset": [0, -1.4],
      },
      paint: {
        "text-color": "#f8fafc",
        "text-halo-color": "#020617",
        "text-halo-width": 2,
      },
    });
  }
}

// Mirrors addMarketZoneLayers's fill+outline pattern (a real, working choropleth
// this codebase already uses for the live market price zones) with new,
// dedicated source/layer IDs -- kept as its own small function rather than
// generalizing addMarketZoneLayers itself, since that function is shared with
// the market-price feature and this is a separate, PyPSA-scenario-specific
// data source. Colors by average_marginal_price_eur_per_mwh, the field
// apps/api's /scenarios/{case_name}/map/regions endpoint attaches to each
// real admin-region polygon.
function addScenarioRegionLayers(
  map: maplibregl.Map,
  data: GeoJSON.FeatureCollection,
  isVisible: boolean,
) {
  if (!map.getSource(SCENARIO_REGIONS_SOURCE_ID)) {
    map.addSource(SCENARIO_REGIONS_SOURCE_ID, {
      type: "geojson",
      data,
    });
  }

  if (!map.getLayer(SCENARIO_REGIONS_FILL_LAYER_ID)) {
    map.addLayer({
      id: SCENARIO_REGIONS_FILL_LAYER_ID,
      type: "fill",
      source: SCENARIO_REGIONS_SOURCE_ID,
      layout: {
        visibility: isVisible ? "visible" : "none",
      },
      paint: {
        "fill-color": [
          "interpolate",
          ["linear"],
          ["coalesce", ["to-number", ["get", "average_marginal_price_eur_per_mwh"]], 0],
          0,
          "#22c55e",
          40,
          "#bef264",
          80,
          "#f59e0b",
          120,
          "#fb7185",
          160,
          "#db2777",
          200,
          "#7c3aed",
        ],
        "fill-opacity": 0.42,
      },
    });
  }

  if (!map.getLayer(SCENARIO_REGIONS_OUTLINE_LAYER_ID)) {
    map.addLayer({
      id: SCENARIO_REGIONS_OUTLINE_LAYER_ID,
      type: "line",
      source: SCENARIO_REGIONS_SOURCE_ID,
      layout: {
        visibility: isVisible ? "visible" : "none",
      },
      paint: {
        "line-color": "#f8fafc",
        "line-opacity": 0.8,
        "line-width": 1.8,
      },
    });
  }
}

function addLayerGroup(
  map: maplibregl.Map,
  sourceId: string,
  data: GeoJSON.FeatureCollection,
  layer: maplibregl.AddLayerObject,
) {
  if (!map.getSource(sourceId)) {
    map.addSource(sourceId, {
      type: "geojson",
      data,
    });
  }

  if (!map.getLayer(layer.id)) {
    map.addLayer(layer);
  }
}

function bringLayerInFront(
  map: maplibregl.Map,
  layerId: string,
  beforeLayerId: string,
) {
  if (!map.getLayer(layerId) || !map.getLayer(beforeLayerId)) {
    return;
  }

  map.moveLayer(layerId, beforeLayerId);
}

function addClusteredPointLayers(
  map: maplibregl.Map,
  config: {
    sourceId: string;
    data: GeoJSON.FeatureCollection;
    clusterLayerId: string;
    clusterCountLayerId: string;
    pointLayerId: string;
    pointColor: string | ExpressionSpecification;
    pointStrokeColor: string;
    clusterColor: string;
    isVisible: boolean;
  },
) {
  if (!map.getSource(config.sourceId)) {
    map.addSource(config.sourceId, {
      type: "geojson",
      data: config.data,
      cluster: true,
      clusterMaxZoom: 7,
      clusterRadius: 42,
    });
  }

  if (!map.getLayer(config.clusterLayerId)) {
    map.addLayer({
      id: config.clusterLayerId,
      type: "circle",
      source: config.sourceId,
      filter: ["has", "point_count"],
      layout: {
        visibility: config.isVisible ? "visible" : "none",
      },
      paint: {
        "circle-color": config.clusterColor,
        "circle-radius": [
          "step",
          ["get", "point_count"],
          18,
          25,
          22,
          100,
          28,
        ],
        "circle-opacity": 0.85,
        "circle-stroke-width": 2,
        "circle-stroke-color": "#020617",
      },
    });
  }

  if (!map.getLayer(config.clusterCountLayerId)) {
    map.addLayer({
      id: config.clusterCountLayerId,
      type: "symbol",
      source: config.sourceId,
      filter: ["has", "point_count"],
      layout: {
        visibility: config.isVisible ? "visible" : "none",
        "text-field": ["get", "point_count_abbreviated"],
        "text-font": ["Open Sans Semibold"],
        "text-size": 12,
      },
      paint: {
        "text-color": "#f8fafc",
      },
    });
  }

  if (!map.getLayer(config.pointLayerId)) {
    map.addLayer({
      id: config.pointLayerId,
      type: "circle",
      source: config.sourceId,
      filter: ["!", ["has", "point_count"]],
      layout: {
        visibility: config.isVisible ? "visible" : "none",
      },
      paint: {
        "circle-radius": [
          "interpolate",
          ["linear"],
          [
            "coalesce",
            ["to-number", ["get", "nominal_capacity_mw"]],
            ["to-number", ["get", "capacity_mw"]],
            0,
          ],
          0,
          4,
          10,
          5,
          50,
          7,
          200,
          10,
          500,
          13,
          1000,
          16,
        ],
        "circle-color": config.pointColor,
        "circle-opacity": 0.72,
        "circle-stroke-width": 2,
        "circle-stroke-color": config.pointStrokeColor,
      },
    });
  }
}

function addSelectedLayers(map: maplibregl.Map) {
  if (!map.getSource(SELECTED_SOURCE_ID)) {
    map.addSource(SELECTED_SOURCE_ID, {
      type: "geojson",
      data: emptySelection,
    });
  }

  if (!map.getLayer(SELECTED_POLYGONS_LAYER_ID)) {
    map.addLayer({
      id: SELECTED_POLYGONS_LAYER_ID,
      type: "fill",
      source: SELECTED_SOURCE_ID,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: {
        "fill-color": "#f8fafc",
        "fill-opacity": 0.28,
      },
    });
  }

  if (!map.getLayer(SELECTED_POLYGON_OUTLINE_LAYER_ID)) {
    map.addLayer({
      id: SELECTED_POLYGON_OUTLINE_LAYER_ID,
      type: "line",
      source: SELECTED_SOURCE_ID,
      filter: ["==", ["geometry-type"], "Polygon"],
      paint: {
        "line-color": "#ffffff",
        "line-width": 3,
      },
    });
  }

  if (!map.getLayer(SELECTED_LINES_LAYER_ID)) {
    map.addLayer({
      id: SELECTED_LINES_LAYER_ID,
      type: "line",
      source: SELECTED_SOURCE_ID,
      filter: ["==", ["geometry-type"], "LineString"],
      paint: {
        "line-color": "#ffffff",
        "line-width": 6,
      },
    });
  }

  if (!map.getLayer(SELECTED_POINTS_LAYER_ID)) {
    map.addLayer({
      id: SELECTED_POINTS_LAYER_ID,
      type: "circle",
      source: SELECTED_SOURCE_ID,
      filter: ["==", ["geometry-type"], "Point"],
      paint: {
        "circle-radius": 10,
        "circle-color": "#ffffff",
        "circle-stroke-width": 3,
        "circle-stroke-color": "#0f172a",
      },
    });
  }
}

function updateLayerVisibility(
  map: maplibregl.Map | null,
  isLoaded: boolean,
  layerId: string,
  isVisible: boolean,
) {
  if (!map || !isLoaded || !map.getLayer(layerId)) {
    return;
  }

  map.setLayoutProperty(layerId, "visibility", isVisible ? "visible" : "none");
}

function updateLayerGroupVisibility(
  map: maplibregl.Map | null,
  isLoaded: boolean,
  layerIds: readonly string[],
  isVisible: boolean,
) {
  for (const layerId of layerIds) {
    updateLayerVisibility(map, isLoaded, layerId, isVisible);
  }
}

function updateSelectedFeature(
  map: maplibregl.Map | null,
  selectedAsset: AssetSelection | null,
) {
  if (!map || !map.getSource(SELECTED_SOURCE_ID)) {
    return;
  }

  const selectedSource = map.getSource(SELECTED_SOURCE_ID) as maplibregl.GeoJSONSource;
  selectedSource.setData(
    selectedAsset
      ? {
          type: "FeatureCollection",
          features: [selectedAsset.feature],
        }
      : emptySelection,
  );
}

function updateGeoJsonSource(
  map: maplibregl.Map | null,
  isLoaded: boolean,
  sourceId: string,
  data: GeoJSON.FeatureCollection,
) {
  if (!map || !isLoaded || !map.getSource(sourceId)) {
    return;
  }

  const source = map.getSource(sourceId) as maplibregl.GeoJSONSource;
  source.setData(data);
}

function updateMarketLineStyle(
  map: maplibregl.Map | null,
  isLoaded: boolean,
  highlightMarketSignal: boolean,
  marketFlowDirection: MarketFlowDirection,
) {
  if (!map || !isLoaded || !map.getLayer(LINES_LAYER_ID)) {
    return;
  }

  const paint = getTransmissionLinePaint(highlightMarketSignal, marketFlowDirection);

  map.setPaintProperty(LINES_LAYER_ID, "line-color", paint["line-color"]);
  map.setPaintProperty(LINES_LAYER_ID, "line-opacity", paint["line-opacity"]);
  map.setPaintProperty(LINES_LAYER_ID, "line-width", paint["line-width"]);
}

function updateMarketZoneStyle(
  map: maplibregl.Map | null,
  isLoaded: boolean,
  highlightMarketSignal: boolean,
  marketPriceEurMwh: number | null,
  marketZoneData: GeoJSON.FeatureCollection,
) {
  if (!map || !isLoaded || !map.getSource(MARKET_ZONE_SOURCE_ID)) {
    return;
  }

  const source = map.getSource(MARKET_ZONE_SOURCE_ID) as maplibregl.GeoJSONSource;
  source.setData(buildMarketZoneData(marketPriceEurMwh, marketZoneData));

  for (const layerId of [
    MARKET_ZONE_FILL_LAYER_ID,
    MARKET_ZONE_OUTLINE_LAYER_ID,
    MARKET_ZONE_LABEL_LAYER_ID,
  ]) {
    updateLayerVisibility(map, isLoaded, layerId, highlightMarketSignal);
  }
}

function focusOnAsset(
  map: maplibregl.Map | null,
  isLoaded: boolean,
  asset: AssetSelection | null,
) {
  if (!map || !isLoaded || !asset) {
    return;
  }

  const geometry = asset.feature.geometry;
  if (geometry.type === "Point") {
    map.flyTo({
      center: geometry.coordinates as [number, number],
      zoom: 10.5,
      essential: true,
    });
    return;
  }

  const bounds = getGeometryBounds(geometry);
  if (!bounds) {
    return;
  }

  map.fitBounds(bounds, {
    padding: 80,
    maxZoom: 11,
    duration: 1200,
    essential: true,
  });
}

function zoomToCluster(
  map: maplibregl.Map,
  event: maplibregl.MapLayerMouseEvent,
  layerId: string,
  sourceId: string,
) {
  const clusterFeature = map.queryRenderedFeatures(event.point, {
    layers: [layerId],
  })[0];

  if (!clusterFeature) {
    return;
  }

  const clusterId = clusterFeature.properties?.cluster_id;
  if (typeof clusterId !== "number") {
    return;
  }

  const source = map.getSource(sourceId) as maplibregl.GeoJSONSource & {
    getClusterExpansionZoom: (
      clusterId: number,
      callback: (error: Error | null, zoom: number) => void,
    ) => void;
  };

  if (!source?.getClusterExpansionZoom) {
    return;
  }

  source.getClusterExpansionZoom(clusterId, (error, zoom) => {
    if (error) {
      return;
    }

    const geometry = clusterFeature.geometry;
    if (geometry.type !== "Point") {
      return;
    }

    map.easeTo({
      center: geometry.coordinates as [number, number],
      zoom,
      duration: 800,
    });
  });
}

function createAssetSelection(feature: maplibregl.MapGeoJSONFeature) {
  const assetType = getAssetType(feature.layer.id);
  if (!assetType) {
    return null;
  }

  const properties = feature.properties ? { ...feature.properties } : {};
  const fallbackId = `${assetType}-${String(feature.id ?? "asset")}`;
  const name = getAssetName(properties, fallbackId);
  const geometry = feature.geometry as GeoJSON.Geometry;

  return {
    id: String(properties.id ?? feature.id ?? fallbackId),
    name,
    assetType,
    properties,
    feature: {
      type: "Feature",
      properties,
      geometry,
    },
  } satisfies AssetSelection;
}

function pickFeatureAtClick(features: maplibregl.MapGeoJSONFeature[]) {
  for (const layerId of [
    PLANTS_LAYER_ID,
    SUBSTATIONS_LAYER_ID,
    LINES_LAYER_ID,
    GAS_IMPORT_POINTS_LAYER_ID,
    GAS_PIPELINES_LAYER_ID,
    HYDROGEN_PIPELINES_LAYER_ID,
    HYDROGEN_PROJECTS_LAYER_ID,
    CELLS_LAYER_ID,
  ]) {
    const matchingFeature = features.find((feature) => feature.layer.id === layerId);
    if (matchingFeature) {
      return matchingFeature;
    }
  }

  return null;
}

function getAssetType(layerId: string): AssetType | null {
  if (layerId === PLANTS_LAYER_ID) {
    return "plant";
  }

  if (layerId === SUBSTATIONS_LAYER_ID) {
    return "substation";
  }

  if (layerId === LINES_LAYER_ID) {
    return "line";
  }

  if (layerId === CELLS_LAYER_ID) {
    return "cell";
  }

  if (layerId === GAS_PIPELINES_LAYER_ID) {
    return "gasPipeline";
  }

  if (layerId === GAS_IMPORT_POINTS_LAYER_ID) {
    return "gasImportPoint";
  }

  if (layerId === HYDROGEN_PIPELINES_LAYER_ID) {
    return "hydrogenPipeline";
  }

  if (layerId === HYDROGEN_PROJECTS_LAYER_ID) {
    return "hydrogenProject";
  }

  return null;
}

function getAssetName(properties: Record<string, unknown>, fallbackId: string) {
  const name = properties.name;
  if (typeof name === "string" && name.trim().length > 0) {
    return name;
  }

  return fallbackId;
}

function getGeometryBounds(geometry: GeoJSON.Geometry) {
  // GeometryCollection has no .coordinates; the layers here only carry
  // Point/Line/Polygon features.
  if (geometry.type === "GeometryCollection") {
    return null;
  }

  const coordinates = collectCoordinates(geometry.coordinates);
  if (coordinates.length === 0) {
    return null;
  }

  let minLng = coordinates[0][0];
  let minLat = coordinates[0][1];
  let maxLng = coordinates[0][0];
  let maxLat = coordinates[0][1];

  for (const [lng, lat] of coordinates) {
    minLng = Math.min(minLng, lng);
    minLat = Math.min(minLat, lat);
    maxLng = Math.max(maxLng, lng);
    maxLat = Math.max(maxLat, lat);
  }

  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ] as [[number, number], [number, number]];
}

function collectCoordinates(value: GeoJSON.Position | GeoJSON.Position[] | GeoJSON.Position[][] | GeoJSON.Position[][][]): [number, number][] {
  if (typeof value[0] === "number") {
    return [value as [number, number]];
  }

  return (value as Array<GeoJSON.Position | GeoJSON.Position[] | GeoJSON.Position[][]>).flatMap(
    (entry) => collectCoordinates(entry),
  );
}

function getViewportBounds(map: maplibregl.Map): ViewportBounds {
  const bounds = map.getBounds();

  return {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
  };
}

function getPlantTechnologyColorExpression(): ExpressionSpecification {
  return [
    "match",
    ["get", "technology_category"],
    "Solar",
    "#facc15",
    "Wind",
    "#60a5fa",
    "Hydro",
    "#14b8a6",
    "Storage",
    "#8b5cf6",
    "Gas",
    "#f97316",
    "Lignite",
    "#92400e",
    "Oil",
    "#dc2626",
    "Biomass/Biogas",
    "#84cc16",
    "CHP",
    "#f59e0b",
    "Geothermal",
    "#ef4444",
    "Other/Unknown",
    "#94a3b8",
    "#94a3b8",
  ];
}

function getTransmissionLinePaint(
  highlightMarketSignal: boolean,
  marketFlowDirection?: MarketFlowDirection,
): NonNullable<LineLayerSpecification["paint"]> {
  return {
    "line-color":
      highlightMarketSignal && marketFlowDirection
        ? getMarketLineColor(marketFlowDirection)
        : "#67e8f9",
    "line-opacity": highlightMarketSignal ? 0.82 : 0.35,
    "line-width": highlightMarketSignal
      ? [
          "interpolate",
          ["linear"],
          ["zoom"],
          5,
          1.8,
          7,
          2.6,
          10,
          4,
        ]
      : [
          "interpolate",
          ["linear"],
          ["zoom"],
          5,
          0.8,
          7,
          1.2,
          10,
          2.2,
        ],
  };
}

function getGasPipelinePaint(): LineLayerSpecification["paint"] {
  return {
    "line-color": "#f59e0b",
    "line-opacity": 0.92,
    "line-width": [
      "interpolate",
      ["linear"],
      ["zoom"],
      5,
      2.2,
      7,
      3.2,
      10,
      5,
    ],
    "line-dasharray": [3.5, 1.2],
  };
}

function getGasPipelineCasingPaint(): LineLayerSpecification["paint"] {
  return {
    "line-color": "#451a03",
    "line-opacity": 0.9,
    "line-width": [
      "interpolate",
      ["linear"],
      ["zoom"],
      5,
      3.4,
      7,
      4.8,
      10,
      7,
    ],
  };
}

function getGasImportPointPaint(): CircleLayerSpecification["paint"] {
  return {
    "circle-radius": [
      "interpolate",
      ["linear"],
      ["zoom"],
      5,
      6,
      8,
      8,
      10,
      10,
    ],
    "circle-color": "#fbbf24",
    "circle-opacity": 0.95,
    "circle-stroke-width": 3,
    "circle-stroke-color": "#451a03",
  };
}

function getHydrogenPipelinePaint(): LineLayerSpecification["paint"] {
  return {
    "line-color": [
      "match",
      ["get", "pipeline_category"],
      "CSV Test Alignment",
      "#67e8f9",
      "#22d3ee",
    ],
    "line-opacity": [
      "case",
      ["==", ["get", "pipeline_category"], "CSV Test Alignment"],
      0.98,
      0.95,
    ],
    "line-width": [
      "interpolate",
      ["linear"],
      ["zoom"],
      5,
      2.2,
      7,
      3.4,
      10,
      5.2,
    ],
    "line-dasharray": [2.2, 1.1],
  };
}

function getHydrogenPipelineCasingPaint(): LineLayerSpecification["paint"] {
  return {
    "line-color": "#083344",
    "line-opacity": 0.92,
    "line-width": [
      "interpolate",
      ["linear"],
      ["zoom"],
      5,
      3.4,
      7,
      4.8,
      10,
      7,
    ],
  };
}

function getHydrogenProjectPaint(): CircleLayerSpecification["paint"] {
  return {
    "circle-radius": [
      "interpolate",
      ["linear"],
      ["coalesce", ["to-number", ["get", "electrolyzer_capacity_mw"]], 0],
      0,
      6,
      10,
      8,
      50,
      11,
      100,
      14,
    ],
    "circle-color": "#22d3ee",
    "circle-opacity": 0.82,
    "circle-stroke-width": 2,
    "circle-stroke-color": "#083344",
  };
}

function getMarketLineColor(direction: MarketFlowDirection) {
  if (direction === "import") {
    return "#38bdf8";
  }

  if (direction === "export") {
    return "#f59e0b";
  }

  if (direction === "balanced") {
    return "#facc15";
  }

  return "#e5e7eb";
}

function getMarketPriceFillColorExpression(): ExpressionSpecification {
  return [
    "case",
    ["==", ["get", "market_status"], "unavailable"],
    "#64748b",
    [
      "interpolate",
      ["linear"],
      ["coalesce", ["to-number", ["get", "price_eur_mwh"]], 0],
      0,
      "#22c55e",
      80,
      "#bef264",
      160,
      "#f59e0b",
      240,
      "#fb7185",
      320,
      "#db2777",
      400,
      "#7c3aed",
    ],
  ];
}

function buildMarketZoneData(
  price: number | null,
  marketZoneData: GeoJSON.FeatureCollection,
): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: marketZoneData.features.map((feature) => ({
      ...feature,
      properties: {
        ...(feature.properties ?? {}),
        price_eur_mwh: price,
        price_label: formatMarketPrice(price),
        market_status: typeof price === "number" ? "available" : "unavailable",
      },
    })),
  };
}

function getMarketDirectionLabel(direction: MarketFlowDirection) {
  if (direction === "import") {
    return "Greece net importing";
  }

  if (direction === "export") {
    return "Greece net exporting";
  }

  if (direction === "balanced") {
    return "Greece balanced";
  }

  return "Market signal awaiting API data";
}

function formatMarketPrice(price: number | null) {
  return typeof price === "number" ? `€${price}/MWh` : "Price unavailable";
}
