"use client";

import type {
  GreeceMarketSignalResponse,
  MarketRequestState,
} from "../types/market";

type MarketPanelProps = {
  enabled: boolean;
  marketSignal: GreeceMarketSignalResponse | null;
  requestState: MarketRequestState;
  errorMessage: string;
  onToggle: (enabled: boolean) => void;
  onRefresh: () => void;
};

export default function MarketPanel({
  enabled,
  marketSignal,
  requestState,
  errorMessage,
  onToggle,
  onRefresh,
}: MarketPanelProps) {
  return (
    <section className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Market Signal
      </h2>

      <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
        <label className="flex items-start gap-3 text-sm text-zinc-100">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => onToggle(event.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-white/20 bg-zinc-800 text-emerald-400 focus:ring-emerald-400"
          />
          <span>
            Highlight Greece price and import/export signal
            <span className="mt-1 block text-xs leading-5 text-zinc-400">
              Uses public IPTO/ADMIE current market and interconnection data.
            </span>
          </span>
        </label>

        {enabled ? (
          <div className="mt-4 space-y-4">
            <button
              type="button"
              onClick={onRefresh}
              disabled={requestState === "loading"}
              className="w-full rounded-lg border border-white/10 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 transition hover:bg-zinc-900 disabled:cursor-not-allowed disabled:text-zinc-500"
            >
              {requestState === "loading" ? "Loading market signal..." : "Refresh market signal"}
            </button>

            {requestState === "error" ? (
              <div className="rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-3">
                <p className="text-sm text-rose-300">{errorMessage}</p>
              </div>
            ) : null}

            {marketSignal ? (
              <div className="rounded-lg border border-white/10 bg-zinc-950/70 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                      Greece Market
                    </p>
                    <p className="mt-2 text-sm leading-6 text-zinc-100">
                      {marketSignal.summary}
                    </p>
                  </div>
                  <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-300">
                    {formatStatus(marketSignal.status)}
                  </span>
                </div>

                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <Metric
                    label={marketSignal.currentPrice.label}
                    value={formatPrice(marketSignal.currentPrice.valueEurMwh)}
                  />
                  <Metric
                    label="Net position"
                    value={formatNetPosition(marketSignal.netImportMw)}
                  />
                  <Metric
                    label="Imports"
                    value={`${marketSignal.totalImportMw} MW`}
                  />
                  <Metric
                    label="Exports"
                    value={`${marketSignal.totalExportMw} MW`}
                  />
                </dl>

                {marketSignal.flows.length > 0 ? (
                  <div className="mt-4 border-t border-white/10 pt-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
                      Cross-border Flows
                    </p>
                    <div className="mt-3 max-h-36 space-y-2 overflow-y-auto">
                      {marketSignal.flows.map((flow) => (
                        <div
                          key={`${flow.zone}-${flow.direction}`}
                          className="flex items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs"
                        >
                          <span className="text-zinc-200">{flow.zone}</span>
                          <span className={flow.direction === "import" ? "text-sky-300" : "text-amber-300"}>
                            {flow.direction} {flow.powerMw} MW
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="mt-1 text-zinc-100">{value}</dd>
    </div>
  );
}

function formatPrice(value: number | null) {
  return typeof value === "number" ? `${value} EUR/MWh` : "Unavailable";
}

function formatNetPosition(value: number) {
  if (value > 0) {
    return `Importing ${value} MW`;
  }

  if (value < 0) {
    return `Exporting ${Math.abs(value)} MW`;
  }

  return "Balanced";
}

function formatStatus(status: string) {
  return status.replace(/_/g, " ");
}
