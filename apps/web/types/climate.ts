export type ClimateRequestState = "idle" | "loading" | "success" | "error";

export type ClimateAssetResponse = {
  source: string;
  latitude: number;
  longitude: number;
  assetTechnology: string;
  current: {
    time: string;
    temperatureC: number | null;
    cloudCoverPct: number | null;
    windSpeed10mKph: number | null;
    windSpeed100mKph: number | null;
    shortwaveRadiationWm2: number | null;
    directNormalIrradianceWm2: number | null;
  };
  efficiency: {
    modeledTechnology: string;
    estimatedEfficiencyPct: number | null;
    band: string;
    summary: string;
  };
  // The real yield model (apps/api/app/site_yield.py): hourly output for this
  // location through a published engineering model, and what it would have
  // earned against the live day-ahead curve. Optional -- absent for a
  // technology this does not model, or when the weather service is down.
  yieldEstimate: SiteYieldEstimate | null;
};

export type SiteYieldEstimate = {
  carrier: string;
  capacityFactorPct: number;
  peakOutputPerUnit: number;
  producingHours: number;
  windowHours: number;
  model: string;
  assumptions: string;
  series: { timestamp: string; outputPerUnit: number }[];
  marketCapture: {
    capturePriceEurMwh: number;
    flatMeanEurMwh: number;
    captureRatePct: number | null;
    matchedHours: number;
    priceSource: string;
    redistributionAllowed: boolean;
  } | null;
};
