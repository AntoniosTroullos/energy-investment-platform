"use client";

export type ViewMode = "explorer" | "analysis";

type ModeToggleProps = {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
};

export default function ModeToggle({ mode, onChange }: ModeToggleProps) {
  const isExplorerMode = mode === "explorer";

  return (
    <section className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-zinc-500">
        Mode
      </h2>
      <div className="mt-4 rounded-xl border border-white/10 bg-white/5 p-2">
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => onChange("explorer")}
            className={`rounded-lg px-3 py-3 text-sm font-medium transition ${
              isExplorerMode
                ? "border border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                : "border border-white/10 bg-zinc-950 text-zinc-300 hover:bg-zinc-900"
            }`}
          >
            Infrastructure Explorer
          </button>
          <button
            type="button"
            onClick={() => onChange("analysis")}
            className={`rounded-lg px-3 py-3 text-sm font-medium transition ${
              !isExplorerMode
                ? "border border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                : "border border-white/10 bg-zinc-950 text-zinc-300 hover:bg-zinc-900"
            }`}
          >
            Analysis
          </button>
        </div>
        <p className="mt-3 text-xs leading-5 text-zinc-400">
          Infrastructure Explorer is the default national view. Analysis tools stay available when you need candidate screening.
        </p>
      </div>
    </section>
  );
}
