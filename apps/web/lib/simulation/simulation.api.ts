import { apiUrl } from "../config";
import type {
  AssetSimulation,
  DemandResponseRequest,
  DemandResponseResult,
  GenerationRequest,
  StorageRequest,
} from "./simulation.types";

async function post<TRequest, TResponse>(path: string, body: TRequest): Promise<TResponse> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    // The API's own detail is far more useful than a status code: it names
    // the missing price year or the unreachable weather archive.
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") detail = payload.detail;
    } catch {
      // Keep the status-code message.
    }
    throw new Error(detail);
  }
  return (await response.json()) as TResponse;
}

export function simulateGeneration(request: GenerationRequest): Promise<AssetSimulation> {
  return post("/simulation/generation", request);
}

export function simulateStorage(request: StorageRequest): Promise<AssetSimulation> {
  return post("/simulation/storage", request);
}

export function simulateDemandResponse(request: DemandResponseRequest): Promise<DemandResponseResult> {
  return post("/simulation/demand-response", request);
}
