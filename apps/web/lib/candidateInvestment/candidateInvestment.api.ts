import { API_BASE_URL } from "../config";
import type {
  CandidateInvestmentAnalysisResponse,
  PortfolioAnalysisResponse,
} from "./candidateInvestment.types";

// Same fetch conventions as lib/pypsaScenario/pypsaScenario.api.ts
// (parseErrorDetail, API_BASE_URL) -- kept as its own small module since this
// is a distinct domain (candidate-site financial analysis), not a PyPSA
// scenario run/result.

async function parseErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export async function getCandidateInvestmentAnalysis(
  caseName: string,
): Promise<CandidateInvestmentAnalysisResponse> {
  const query = new URLSearchParams({ case_name: caseName });
  const response = await fetch(`${API_BASE_URL}/candidates/investment-analysis?${query}`);
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to fetch candidate investment analysis (status ${response.status}).`),
    );
  }
  return (await response.json()) as CandidateInvestmentAnalysisResponse;
}

export async function getPortfolioAnalysis(
  caseName: string,
  candidateIds: string[],
): Promise<PortfolioAnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/candidates/portfolio-analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_name: caseName, candidate_ids: candidateIds }),
  });
  if (!response.ok) {
    throw new Error(
      await parseErrorDetail(response, `Unable to compute portfolio analysis (status ${response.status}).`),
    );
  }
  return (await response.json()) as PortfolioAnalysisResponse;
}
