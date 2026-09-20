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
};
