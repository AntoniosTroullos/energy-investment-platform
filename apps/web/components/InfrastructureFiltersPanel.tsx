"use client";

import {
  PLANT_STATUS_CATEGORIES,
  PLANT_TECHNOLOGY_CATEGORIES,
  getPlantStatusDotClass,
  type PlantStatusCategory,
  type PlantTechnologyCategory,
} from "../lib/plant-categories";

type VoltageOption = {
  value: string;
  label: string;
};

type InfrastructureFiltersPanelProps = {
  enabledPlantTechnologies: PlantTechnologyCategory[];
  onTogglePlantTechnology: (category: PlantTechnologyCategory) => void;
  enabledPlantStatuses: PlantStatusCategory[];
  onTogglePlantStatus: (status: PlantStatusCategory) => void;
  voltageFilter: string;
  onVoltageFilterChange: (value: string) => void;
  voltageOptions: VoltageOption[];
  limitResultsToViewport: boolean;
  onLimitResultsToViewportChange: (checked: boolean) => void;
  plantsInViewCount: number;
  substationsInViewCount: number;
  linesInViewCount: number;
  gasPipelinesInViewCount: number;
  gasImportsInViewCount: number;
  hydrogenPipelinesInViewCount: number;
  hydrogenProjectsInViewCount: number;
};

export default function InfrastructureFiltersPanel({
  enabledPlantTechnologies,
  onTogglePlantTechnology,
  enabledPlantStatuses,
  onTogglePlantStatus,
  voltageFilter,
  onVoltageFilterChange,
  voltageOptions,
  limitResultsToViewport,
  onLimitResultsToViewportChange,
  plantsInViewCount,
  substationsInViewCount,
  linesInViewCount,
  gasPipelinesInViewCount,
  gasImportsInViewCount,
  hydrogenPipelinesInViewCount,
  hydrogenProjectsInViewCount,
}: InfrastructureFiltersPanelProps) {
  return (
    <section className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Infrastructure Filters
      </h2>
      <div className="mt-4 space-y-4">
        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <label
            htmlFor="plant-technology-filter"
            className="text-sm font-medium text-zinc-100"
          >
            Plant Technologies
          </label>
          <div className="mt-3 space-y-2">
            {PLANT_TECHNOLOGY_CATEGORIES.map((category) => {
              const checked = enabledPlantTechnologies.includes(category);

              return (
                <label
                  key={category}
                  className="flex items-center gap-3 rounded-lg border border-white/10 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-200"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onTogglePlantTechnology(category)}
                    className="h-4 w-4 rounded border-white/20 bg-zinc-800 text-emerald-400 focus:ring-emerald-400"
                  />
                  <span>{category}</span>
                </label>
              );
            })}
          </div>
          <p className="mt-3 text-xs leading-5 text-zinc-400">
            Layer toggles above control visibility, while these checkboxes limit plants by normalized technology category.
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <label className="text-sm font-medium text-zinc-100">
            Plant Status
          </label>
          <div className="mt-3 space-y-2">
            {PLANT_STATUS_CATEGORIES.map((status) => {
              const checked = enabledPlantStatuses.includes(status);

              return (
                <label
                  key={status}
                  className="flex items-center gap-3 rounded-lg border border-white/10 bg-zinc-950/60 px-3 py-2 text-sm text-zinc-200"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onTogglePlantStatus(status)}
                    className="h-4 w-4 rounded border-white/20 bg-zinc-800 text-emerald-400 focus:ring-emerald-400"
                  />
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${getPlantStatusDotClass(status)}`}
                  />
                  <span>{status}</span>
                </label>
              );
            })}
          </div>
          <p className="mt-3 text-xs leading-5 text-zinc-400">
            Use these checkboxes to focus on operating, announced, or under-construction generators without changing the rest of the explorer.
          </p>
        </div>

        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
          <label
            htmlFor="voltage-filter"
            className="text-sm font-medium text-zinc-100"
          >
            Voltage
          </label>
          <select
            id="voltage-filter"
            value={voltageFilter}
            onChange={(event) => onVoltageFilterChange(event.target.value)}
            className="mt-3 w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-3 text-sm text-zinc-100 outline-none focus:border-emerald-400"
          >
            <option value="all">All voltages</option>
            {voltageOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="mt-3 text-xs leading-5 text-zinc-400">
            Applies to substations and transmission lines when voltage data is available.
          </p>
        </div>

        <label className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/5 px-4 py-4 text-sm text-zinc-100">
          <input
            type="checkbox"
            checked={limitResultsToViewport}
            onChange={(event) => onLimitResultsToViewportChange(event.target.checked)}
            className="h-4 w-4 rounded border-white/20 bg-zinc-800 text-emerald-400 focus:ring-emerald-400"
          />
          <span>Limit results to current map view</span>
        </label>

        <div className="rounded-xl border border-white/10 bg-zinc-950/90 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
            In View
          </p>
          <div className="mt-4 space-y-2 text-sm text-zinc-100">
            <p>Plants in view: {plantsInViewCount}</p>
            <p>Substations in view: {substationsInViewCount}</p>
            <p>Transmission lines in view: {linesInViewCount}</p>
            <p>Gas pipelines in view: {gasPipelinesInViewCount}</p>
            <p>Gas import points in view: {gasImportsInViewCount}</p>
            <p>Hydrogen pipelines in view: {hydrogenPipelinesInViewCount}</p>
            <p>Hydrogen projects in view: {hydrogenProjectsInViewCount}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
