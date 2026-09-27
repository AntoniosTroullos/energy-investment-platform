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
