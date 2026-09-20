# Regional Demand Allocation Frontend Build Brief

## Goal

Add a read-only frontend layer that visualizes the backend regional allocation model:

```text
national Greek load -> estimated regional allocation -> map polygons + sidebar table
```

Use this wording everywhere:

```text
Estimated regional demand allocation
```

Do not call it measured regional demand. The values are model allocations from national load and regional proxies.

## Backend Endpoint

Endpoint:

```text
GET http://127.0.0.1:8000/regional-demand/allocation
```

Optional query parameters:

```text
timestamp_utc=2026-08-01T12:00:00Z
national_load_mw=8500
```

Default behavior:

- If `national_load_mw` is omitted, backend uses latest local model-ready IPTO/ADMIE national load.
- If `timestamp_utc` is omitted, backend uses latest local model-ready IPTO/ADMIE timestamp.
- If `national_load_mw` is supplied but timestamp is omitted, latest local timestamp still controls month/season.

Known verification payload:

```text
/regional-demand/allocation?timestamp_utc=2026-08-01T12:00:00Z&national_load_mw=8500
```

Expected:

```text
month: 8
season: summer
regions: 13
regionsGeojson.features: 13
sum(regions[].allocatedLoadMw): 8500.0
top region: Attica
Crete and South_Aegean visibly increase through commercial/tourism share
```

## TypeScript Types

Create:

```text
apps/web/types/regional-demand.ts
```

Contents:

```ts
export type RegionalDemandRequestState = "idle" | "loading" | "success" | "error";

export type RegionalDemandRow = {
  regionId: string;
  geo: string;
  allocatedLoadMw: number;
  allocationShare: number;
  residentialShare: number;
  commercialShare: number;
  industrialShare: number;
  agriculturalShare: number;
  publicShare: number;
  dominantDriver: string;
  month: number;
  season: string;
};

export type RegionalDemandAllocationResponse = {
  timestampUtc: string;
  nationalLoadMw: number;
  month: number;
  season: string;
  method: string;
  source: string;
  regions: RegionalDemandRow[];
  regionsGeojson: GeoJSON.FeatureCollection;
};
```

## Sidebar Panel

Create:

```text
apps/web/components/RegionalDemandPanel.tsx
```

Match the existing `MarketPanel` styling:

- section title: `Regional Demand`
- outer panel: `rounded-xl border border-white/10 bg-white/5 p-4`
- checkbox toggle
- refresh button
- compact status/error card
- compact metrics grid
- scrollable top-region table

Props:

```ts
type RegionalDemandPanelProps = {
  enabled: boolean;
  allocation: RegionalDemandAllocationResponse | null;
  requestState: RegionalDemandRequestState;
  errorMessage: string;
  onToggle: (enabled: boolean) => void;
  onRefresh: () => void;
};
```

Panel copy:

```text
Estimated regional demand allocation
Uses national Greek load and Eurostat regional proxies.
```

Metrics:

```text
National load: format MW, no more than 1 decimal
Timestamp: local readable timestamp
Month/season
Regions: 13
```

Top table columns:

```text
Region | MW | Share | Driver
```

Show the top 6 regions sorted by `allocatedLoadMw` descending. Use `allocation.regions`, which the backend already returns sorted, but sort defensively in the component.

Formatting helpers:

```ts
function formatMw(value: number) {
  return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} MW`;
}

function formatPct(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}
```

## page.tsx Wiring

In:

```text
apps/web/app/page.tsx
```

Add import:

```ts
import RegionalDemandPanel from "../components/RegionalDemandPanel";
import type {
  RegionalDemandAllocationResponse,
  RegionalDemandRequestState,
} from "../types/regional-demand";
```

Add constant near other API URLs:

```ts
const REGIONAL_DEMAND_API_URL = "http://127.0.0.1:8000/regional-demand/allocation";
```

Add state:

```ts
const [regionalDemandEnabled, setRegionalDemandEnabled] = useState(false);
const [regionalDemandAllocation, setRegionalDemandAllocation] =
  useState<RegionalDemandAllocationResponse | null>(null);
const [regionalDemandRequestState, setRegionalDemandRequestState] =
  useState<RegionalDemandRequestState>("idle");
const [regionalDemandErrorMessage, setRegionalDemandErrorMessage] = useState("");
```

Add effect:

```ts
useEffect(() => {
  if (!regionalDemandEnabled) {
    return;
  }

  void loadRegionalDemandAllocation();
}, [regionalDemandEnabled]);
```

Add loader:

```ts
async function loadRegionalDemandAllocation() {
  setRegionalDemandRequestState("loading");
  setRegionalDemandErrorMessage("");

  try {
    const response = await fetch(REGIONAL_DEMAND_API_URL);

    if (!response.ok) {
      setRegionalDemandRequestState("error");
      setRegionalDemandErrorMessage(
        "Regional demand allocation failed. Backend unavailable or returned an error.",
      );
      return;
    }

    const payload = (await response.json()) as RegionalDemandAllocationResponse;
    setRegionalDemandAllocation(payload);
    setRegionalDemandRequestState("success");
  } catch {
    setRegionalDemandRequestState("error");
    setRegionalDemandErrorMessage("Could not reach regional demand service.");
  }
}
```

Add panel below `MarketPanel`:

```tsx
<RegionalDemandPanel
  enabled={regionalDemandEnabled}
  allocation={regionalDemandAllocation}
  requestState={regionalDemandRequestState}
  errorMessage={regionalDemandErrorMessage}
  onToggle={setRegionalDemandEnabled}
  onRefresh={loadRegionalDemandAllocation}
/>
```

Pass into `MapView`:

```tsx
showRegionalDemand={regionalDemandEnabled}
regionalDemandData={
  regionalDemandAllocation?.regionsGeojson ?? emptyFeatureCollection
}
```

## LayerControlPanel

In:

```text
apps/web/components/LayerControlPanel.tsx
```

Add to `LayerKey`:

```ts
| "regionalDemand"
```

Add to `context` group or `analysis` group. Recommended:

```ts
{
  id: "context",
  title: "Context",
  count: 2,
  defaultOpen: false,
  items: [
    { key: "natura2000", label: "Natura 2000" },
    { key: "regionalDemand", label: "Regional Demand Allocation" },
  ],
}
```

In `page.tsx`, add it to `visibilityState`:

```ts
regionalDemand: [regionalDemandEnabled, setRegionalDemandEnabled],
```

This gives the layer a standard checkbox in the existing layer panel and avoids a second independent map toggle.

## MapView Changes

In:

```text
apps/web/components/MapView.tsx
```

Add props:

```ts
showRegionalDemand: boolean;
regionalDemandData: GeoJSON.FeatureCollection;
```

Add constants:

```ts
const REGIONAL_DEMAND_SOURCE_ID = "regional-demand-source";
const REGIONAL_DEMAND_FILL_LAYER_ID = "regional-demand-fill-layer";
const REGIONAL_DEMAND_OUTLINE_LAYER_ID = "regional-demand-outline-layer";
const REGIONAL_DEMAND_LABEL_LAYER_ID = "regional-demand-label-layer";
```

Add refs/effects matching other GeoJSON layers:

```ts
const showRegionalDemandRef = useRef(showRegionalDemand);
const regionalDemandDataRef = useRef(regionalDemandData);
```

Use standard update effects:

```ts
useEffect(() => {
  showRegionalDemandRef.current = showRegionalDemand;
}, [showRegionalDemand]);

useEffect(() => {
  regionalDemandDataRef.current = regionalDemandData;
}, [regionalDemandData]);

useEffect(() => {
  updateLayerVisibility(mapRef.current, isMapLoadedRef.current, REGIONAL_DEMAND_FILL_LAYER_ID, showRegionalDemand);
  updateLayerVisibility(mapRef.current, isMapLoadedRef.current, REGIONAL_DEMAND_OUTLINE_LAYER_ID, showRegionalDemand);
  updateLayerVisibility(mapRef.current, isMapLoadedRef.current, REGIONAL_DEMAND_LABEL_LAYER_ID, showRegionalDemand);
}, [showRegionalDemand]);

useEffect(() => {
  updateGeoJsonSource(
    mapRef.current,
    isMapLoadedRef.current,
    REGIONAL_DEMAND_SOURCE_ID,
    regionalDemandData,
  );
}, [regionalDemandData]);
```

Add layers on map load before points/lines so infrastructure stays above it:

```ts
addRegionalDemandLayers(
  map,
  regionalDemandDataRef.current,
  showRegionalDemandRef.current,
);
```

Layer paint:

```ts
function getRegionalDemandFillColorExpression() {
  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["to-number", ["get", "allocation_share"]], 0],
    0.015,
    "#164e63",
    0.04,
    "#0e7490",
    0.07,
    "#0891b2",
    0.12,
    "#f59e0b",
    0.2,
    "#ef4444",
    0.35,
    "#a21caf",
  ];
}
```

Layer definition:

```ts
function addRegionalDemandLayers(
  map: maplibregl.Map,
  data: GeoJSON.FeatureCollection,
  isVisible: boolean,
) {
  if (!map.getSource(REGIONAL_DEMAND_SOURCE_ID)) {
    map.addSource(REGIONAL_DEMAND_SOURCE_ID, {
      type: "geojson",
      data,
    });
  }

  if (!map.getLayer(REGIONAL_DEMAND_FILL_LAYER_ID)) {
    map.addLayer({
      id: REGIONAL_DEMAND_FILL_LAYER_ID,
      type: "fill",
      source: REGIONAL_DEMAND_SOURCE_ID,
      layout: { visibility: isVisible ? "visible" : "none" },
      paint: {
        "fill-color": getRegionalDemandFillColorExpression(),
        "fill-opacity": 0.44,
      },
    });
  }

  if (!map.getLayer(REGIONAL_DEMAND_OUTLINE_LAYER_ID)) {
    map.addLayer({
      id: REGIONAL_DEMAND_OUTLINE_LAYER_ID,
      type: "line",
      source: REGIONAL_DEMAND_SOURCE_ID,
      layout: { visibility: isVisible ? "visible" : "none" },
      paint: {
        "line-color": "#e2e8f0",
        "line-opacity": 0.72,
        "line-width": 1.4,
      },
    });
  }

  if (!map.getLayer(REGIONAL_DEMAND_LABEL_LAYER_ID)) {
    map.addLayer({
      id: REGIONAL_DEMAND_LABEL_LAYER_ID,
      type: "symbol",
      source: REGIONAL_DEMAND_SOURCE_ID,
      minzoom: 6,
      layout: {
        visibility: isVisible ? "visible" : "none",
        "text-field": [
          "concat",
          ["get", "name"],
          "\n",
          ["to-string", ["round", ["get", "allocation_pct"]]],
          "%",
        ],
        "text-font": ["Open Sans Semibold"],
        "text-size": 11,
        "text-allow-overlap": false,
      },
      paint: {
        "text-color": "#f8fafc",
        "text-halo-color": "#020617",
        "text-halo-width": 1.8,
      },
    });
  }
}
```

Do not add regional demand polygons to `CLICKABLE_LAYER_IDS` in the first frontend pass. Keep asset selection behavior unchanged. Use hover popup later if desired; the sidebar table is enough for v1.

Add a small legend overlay only when enabled, following the existing market overlay pattern:

```tsx
{showRegionalDemand ? <RegionalDemandMapLegend /> : null}
```

Legend copy:

```text
Estimated regional demand share
Low -> High
```

Keep it bottom-left or top-left opposite the existing market overlay so they do not overlap if both are enabled.

## Acceptance Checks

Backend must be running:

```text
cd apps/api
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend build:

```text
cd apps/web
npm.cmd run build
```

Manual browser check:

1. Start backend and frontend.
2. Toggle `Regional Demand Allocation` from Layers.
3. Panel loads without error.
4. Greece regions render as polygons.
5. Top table shows 13-region backend payload, sorted by MW.
6. Map layer hides when toggle is off.
7. Existing plants/substations/lines/candidate-cell selection still works.
8. Market signal layer can be toggled independently.

Scientific/UX check:

- Panel and map never say `measured regional demand`.
- Source text says national load + Eurostat regional proxies.
- Values are formatted for humans, but raw backend precision is not modified in state.
- The regional layer is visual/contextual only; it must not change scenario scoring in this pass.

## Backend Verification Already Completed

```text
cd apps/api
..\..\.venv\Scripts\python.exe -m unittest discover -s tests

Ran 72 tests in 37.864s
OK
```

