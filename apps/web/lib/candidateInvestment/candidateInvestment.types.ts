// Mirrors apps/api's CandidateInvestmentAnalysis / CandidateInvestmentAnalysisResponse
// (app/models.py) -- see app/investment_analysis.py for how each field is
// computed and what is a real solved-scenario result vs. a named external
// assumption (the `assumptions` block below states which is which).

export type CandidateInvestmentAnalysis = {
  candidate_id: string;
  technology: string;
  carrier: string | null;
  region_id: string | null;
  assumed_capacity_mw: number | null;
  capex_eur: number | null;
  annual_generation_year0_mwh: number | null;
  captured_price_eur_per_mwh: number | null;
  lcoe_eur_per_mwh: number | null;
  npv_eur: number | null;
  irr_pct: number | null;
  payback_years: number | null;
  message: string | null;
};

export type CandidateInvestmentAnalysisResponse = {
  case_name: string;
  target_year: number;
  analyses: CandidateInvestmentAnalysis[];
  assumptions: Record<string, string>;
};

// ---------------------------------------------------------------------------
// Portfolio analysis -- POST /candidates/portfolio-analysis. Portfolio IRR is
// NOT an average of each candidate's own IRR (averaging IRRs across
// investments is not mathematically valid) -- it's computed server-side from
// the combined annual cash-flow stream. See apps/api's
// investment_analysis.py's combine_cash_flows.
// ---------------------------------------------------------------------------

export type PortfolioCandidateSummary = {
  candidate_id: string;
  technology: string;
  carrier: string | null;
  region_id: string | null;
  assumed_capacity_mw: number | null;
  capex_eur: number | null;
  npv_eur: number | null;
  irr_pct: number | null;
  message: string | null;
};

export type PortfolioBreakdownEntry = {
  label: string;
  capex_eur: number;
  assumed_capacity_mw: number;
  candidate_count: number;
  capex_share_pct: number;
};

export type PortfolioAnalysisResponse = {
  case_name: string;
  target_year: number;
  candidates: PortfolioCandidateSummary[];
  included_count: number;
  excluded_count: number;
  total_capex_eur: number | null;
  total_assumed_capacity_mw: number | null;
  total_npv_eur: number | null;
  portfolio_irr_pct: number | null;
  portfolio_payback_years: number | null;
  technology_breakdown: PortfolioBreakdownEntry[];
  region_breakdown: PortfolioBreakdownEntry[];
  concentration_flags: string[];
  assumptions: Record<string, string>;
};
