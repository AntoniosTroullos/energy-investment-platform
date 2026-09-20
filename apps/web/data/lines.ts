// Mock transmission lines so we can test line rendering before real network data exists.
export const linesData = {
  type: "FeatureCollection" as const,
  features: [
    {
      type: "Feature" as const,
      properties: {
        id: "line-central-400",
        name: "Central Corridor",
        status: "Operating",
        voltage_kv: 400,
      },
      geometry: {
        type: "LineString" as const,
        coordinates: [
          [21.73, 38.25],
          [22.42, 39.64],
          [23.72, 38.05],
        ],
      },
    },
  ],
};
