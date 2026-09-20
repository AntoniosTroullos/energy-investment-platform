export type MarketRequestState = "idle" | "loading" | "success" | "error";

export type MarketFlowDirection = "import" | "export" | "balanced" | "unavailable";

export type GreeceMarketSignalResponse = {
  source: string;
  zone: string;
  status: string;
  currentPrice: {
    valueEurMwh: number | null;
    datetime: string | null;
    temporalGranularity: string | null;
    label: string;
  };
  totalImportMw: number;
  totalExportMw: number;
  netImportMw: number;
  flows: Array<{
    zone: string;
    direction: string;
    powerMw: number;
  }>;
  summary: string;
};
