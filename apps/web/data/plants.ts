// Mock power plant points used to test the map while real data is not connected yet.
export const plantsData = {
  type: "FeatureCollection" as const,
  features: [
    {
      type: "Feature" as const,
      properties: {
        id: "plant-athens-001",
        name: "Athens Plant",
        technology: "Gas",
        status: "Operating",
      },
      geometry: { type: "Point" as const, coordinates: [23.72, 38.05] },
    },
    {
      type: "Feature" as const,
      properties: {
        id: "plant-patras-001",
        name: "Patras Plant",
        technology: "Solar",
        status: "Planned",
      },
      geometry: { type: "Point" as const, coordinates: [21.73, 38.25] },
    },
  ],
};
