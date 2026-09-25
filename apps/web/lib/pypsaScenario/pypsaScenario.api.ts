import { API_BASE_URL } from "../config";
import type {
  CoupledScenarioParams,
  CoupledScenarioResult,
  CoupledScenarioRunResponse,
  ElectricityScenarioResult,
  ElectricityScenarioRunResponse,
  PypsaScenarioParams,
  ScenarioListResponse,
  ScenarioOptions,
  ScenarioStatusResponse,
} from "./pypsaScenario.types";

// Calls the FastAPI backend directly (base URL from lib/config.ts), matching
// the one real, actually-used integration convention in this codebase
// (ScenarioPresetsPanel's "Evaluate Scenario" button does the same) rather
// than proxying through a Next.js API route.

async function parseErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export async function runElectricityScenario(
  params: PypsaScenarioParams,
): Promise<ElectricityScenarioRunResponse> {
  const response = await fetch(`${API_BASE_URL}/scenarios/electricity/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_year: params.targetYear,
      annual_growth_rate: params.annualGrowthRate,
    }),
  });

  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to start the scenario (status ${response.status}).`),
    );
  }

  return (await response.json()) as ElectricityScenarioRunResponse;
}

export async function getScenarioStatus(caseName: string): Promise<ScenarioStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/scenarios/${caseName}/status`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to check scenario status (status ${response.status}).`),
    );
  }
  return (await response.json()) as ScenarioStatusResponse;
}

export async function getScenarioResult(caseName: string): Promise<ElectricityScenarioResult> {
  const response = await fetch(`${API_BASE_URL}/scenarios/${caseName}/result`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to fetch scenario results (status ${response.status}).`),
    );
  }
  return (await response.json()) as ElectricityScenarioResult;
}

export async function getScenarioRegionsGeoJson(caseName: string): Promise<GeoJSON.FeatureCollection> {
  const response = await fetch(`${API_BASE_URL}/scenarios/${caseName}/map/regions`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to fetch the scenario region map (status ${response.status}).`),
    );
  }
  return (await response.json()) as GeoJSON.FeatureCollection;
}

export async function getScenarioList(): Promise<ScenarioListResponse> {
  const response = await fetch(`${API_BASE_URL}/scenarios`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to fetch the scenario library (status ${response.status}).`),
    );
  }
  return (await response.json()) as ScenarioListResponse;
}

export async function getScenarioOptions(): Promise<ScenarioOptions> {
  const response = await fetch(`${API_BASE_URL}/scenarios/options`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to fetch scenario options (status ${response.status}).`),
    );
  }
  return (await response.json()) as ScenarioOptions;
}

export async function getScenarioRegionsDeltaGeoJson(
  caseNameA: string,
  caseNameB: string,
): Promise<GeoJSON.FeatureCollection> {
  const query = new URLSearchParams({ case_a: caseNameA, case_b: caseNameB });
  const response = await fetch(`${API_BASE_URL}/scenarios/compare/map/regions?${query}`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to fetch the scenario comparison map (status ${response.status}).`),
    );
  }
  return (await response.json()) as GeoJSON.FeatureCollection;
}

export async function getNetworkTopologyGeoJson(): Promise<GeoJSON.FeatureCollection> {
  const response = await fetch(`${API_BASE_URL}/scenarios/network-topology`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to fetch the network topology (status ${response.status}).`),
    );
  }
  return (await response.json()) as GeoJSON.FeatureCollection;
}

export async function getGeneratorClustersGeoJson(): Promise<GeoJSON.FeatureCollection> {
  const response = await fetch(`${API_BASE_URL}/generator-clusters`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to fetch generator cluster locations (status ${response.status}).`),
    );
  }
  return (await response.json()) as GeoJSON.FeatureCollection;
}

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_ATTEMPTS = 200; // ~10 minutes at 3s intervals -- a real solve is expected to take well under this

/**
 * Polls scenario status until it reaches a terminal state (done or crashed),
 * calling onTick after every poll so the caller can update a pending UI.
 * Resolves with the terminal status; never resolves on "running"/"not_found".
 */
export async function pollScenarioUntilTerminal(
  caseName: string,
  onTick?: (status: ScenarioStatusResponse) => void,
): Promise<ScenarioStatusResponse> {
  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
    const status = await getScenarioStatus(caseName);
    onTick?.(status);

    if (status.state === "done" || status.state === "crashed") {
      return status;
    }

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }

  throw new Error(
    `Scenario '${caseName}' did not finish within the expected time. It may still be running -- check back later.`,
  );
}

// ---------------------------------------------------------------------------
// Coupled gas/hydrogen/heat scenario (Phase 5). A 428 response means the
// electricity case for the requested year hasn't been solved yet -- surfaced
// via ScenarioPreconditionError, distinct from a generic error.
// ---------------------------------------------------------------------------

export class CoupledScenarioPreconditionError extends Error {}

export async function runCoupledScenario(
  params: CoupledScenarioParams,
): Promise<CoupledScenarioRunResponse> {
  const response = await fetch(`${API_BASE_URL}/scenarios/coupled/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_year: params.targetYear,
      h2_market_scenario: params.h2MarketScenario,
    }),
  });

  if (response.status === 428) {
    throw new CoupledScenarioPreconditionError(
      await parseErrorDetail(response, "The electricity case for this year hasn't been solved yet."),
    );
  }

  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to start the coupled solve (status ${response.status}).`),
    );
  }

  return (await response.json()) as CoupledScenarioRunResponse;
}

export async function getCoupledScenarioStatus(caseName: string): Promise<ScenarioStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/scenarios/${caseName}/coupled/status`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to check the coupled solve status (status ${response.status}).`),
    );
  }
  return (await response.json()) as ScenarioStatusResponse;
}

export async function getCoupledScenarioResult(caseName: string): Promise<CoupledScenarioResult> {
  const response = await fetch(`${API_BASE_URL}/scenarios/${caseName}/coupled/result`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to fetch the coupled solve results (status ${response.status}).`),
    );
  }
  return (await response.json()) as CoupledScenarioResult;
}

/** Mirrors pollScenarioUntilTerminal below, pointed at the coupled status
 * endpoint -- kept as its own function rather than a shared parametrized
 * helper, matching this file's existing per-domain style. */
export async function pollCoupledScenarioUntilTerminal(
  caseName: string,
  onTick?: (status: ScenarioStatusResponse) => void,
): Promise<ScenarioStatusResponse> {
  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
    const status = await getCoupledScenarioStatus(caseName);
    onTick?.(status);

    if (status.state === "done" || status.state === "crashed") {
      return status;
    }

    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }

  throw new Error(
    `Coupled solve for '${caseName}' did not finish within the expected time. It may still be running -- check back later.`,
  );
}
