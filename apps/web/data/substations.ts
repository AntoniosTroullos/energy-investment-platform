// Mock substation points for the early UI and layer-toggle flow.
export const substationsData = {
  type: "FeatureCollection" as const,
  features: [
    {
      type: "Feature" as const,
      properties: {
        id: "sub-athens-150",
        name: "Athens Substation",
        status: "Operating",
        voltage_kv: 150,
      },
      geometry: { type: "Point" as const, coordinates: [23.85, 38.0] },
    },
    {
      type: "Feature" as const,
      properties: {
        id: "sub-larissa-400",
        name: "Larissa Substation",
        status: "Operating",
        voltage_kv: 400,
      },
      geometry: { type: "Point" as const, coordinates: [22.42, 39.64] },
    },
  ],
};
