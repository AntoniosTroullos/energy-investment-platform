"use client";

import { useState } from "react";

type LayerKey =
  | "plants"
  | "substations"
  | "lines"
  | "gasPipelines"
  | "gasImports"
  | "hydrogenPipelines"
  | "hydrogenProjects"
  | "natura2000"
  | "cells"
  | "generatorClusters"
  | "scenarioRegions";

type LayerItem = {
  key: LayerKey;
  label: string;
};

type LayerGroup = {
  id: "infrastructure" | "context" | "analysis" | "scenarioResults";
  title: string;
  count: number;
  defaultOpen: boolean;
  items?: readonly LayerItem[];
  placeholder?: string;
};

type LayerControlPanelProps = {
  mode: "explorer" | "analysis";
  visibilityState: Record<LayerKey, readonly [boolean, (value: boolean) => void]>;
};

const layerGroups: readonly LayerGroup[] = [
  {
    id: "infrastructure",
    title: "Infrastructure",
    count: 7,
    defaultOpen: true,
    items: [
      { key: "plants", label: "Power Plants" },
      { key: "substations", label: "Substations" },
      { key: "lines", label: "Transmission Lines" },
      { key: "gasPipelines", label: "Gas Pipelines" },
      { key: "gasImports", label: "Gas Import Points" },
      { key: "hydrogenPipelines", label: "Hydrogen Pipelines" },
      { key: "hydrogenProjects", label: "Hydrogen Projects" },
    ],
  },
  {
    id: "context",
    title: "Context",
    count: 1,
    defaultOpen: false,
    items: [{ key: "natura2000", label: "Natura 2000" }],
  },
  {
    id: "analysis",
    title: "Analysis",
    count: 1,
    defaultOpen: true,
    items: [{ key: "cells", label: "Suitability Cells" }],
  },
  {
    id: "scenarioResults",
    title: "Scenario Results",
    count: 2,
    defaultOpen: false,
    items: [
      { key: "generatorClusters", label: "Real Asset Clusters (capacity)" },
      { key: "scenarioRegions", label: "Solved Scenario (price / generation)" },
    ],
  },
] as const;

export default function LayerControlPanel({
  mode,
  visibilityState,
}: LayerControlPanelProps) {
  const [openSections, setOpenSections] = useState({
    infrastructure: layerGroups[0].defaultOpen,
    context: layerGroups[1].defaultOpen,
    analysis: layerGroups[2].defaultOpen,
    scenarioResults: layerGroups[3].defaultOpen,
  });

  const visibleGroups =
    mode === "explorer"
      ? layerGroups.filter((group) => group.id !== "analysis" && group.id !== "scenarioResults")
      : layerGroups;

  return (
    <section className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Layers
      </h2>

      <div className="mt-4 space-y-4">
        {visibleGroups.map((group) => {
          const isOpen = openSections[group.id];

          return (
            <div
              key={group.id}
              className="rounded-xl border border-white/10 bg-white/5"
            >
              <button
                type="button"
                onClick={() =>
                  setOpenSections((current) => ({
                    ...current,
                    [group.id]: !current[group.id],
                  }))
                }
                className="flex w-full items-center justify-between px-4 py-3 text-left"
              >
                <div>
                  <p className="text-sm font-medium text-zinc-100">
                    {group.title} ({group.count})
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    {isOpen ? "Hide layers" : "Show layers"}
                  </p>
                </div>
                <span className="text-lg leading-none text-zinc-500">
                  {isOpen ? "-" : "+"}
                </span>
              </button>

              {isOpen ? (
                <div className="border-t border-white/10 px-4 py-4">
                  {group.items ? (
                    <div className="space-y-3">
                      {group.items.map((layer) => {
                        const [checked, setChecked] = visibilityState[layer.key];

                        return (
                          <label
                            key={layer.key}
                            className="flex items-center gap-3 rounded-lg border border-white/10 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-200"
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(event) => setChecked(event.target.checked)}
                              className="h-4 w-4 rounded border-white/20 bg-zinc-800 text-emerald-400 focus:ring-emerald-400"
                            />
                            <span>{layer.label}</span>
                          </label>
                        );
                      })}
                    </div>
                  ) : (
                    <p className="text-sm text-zinc-400">{group.placeholder}</p>
                  )}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
