import type { LucideIcon } from "lucide-react";

// A headline figure. `hint` carries the one thing that stops the number being
// misread -- what it is a figure OF -- because on a grid dashboard "capacity"
// alone could mean the operating fleet or the licensing pipeline, and the two
// differ by an order of magnitude.

type KpiTileProps = {
  label: string;
  value: string;
  hint?: string;
  icon: LucideIcon;
  tone?: "default" | "positive" | "warning";
  bar?: { fraction: number; label?: string };
};

const TONE_CLASSES = {
  default: { icon: "text-emerald-400", ring: "ring-emerald-500/20 bg-emerald-500/10" },
  positive: { icon: "text-emerald-300", ring: "ring-emerald-400/30 bg-emerald-400/10" },
  warning: { icon: "text-amber-300", ring: "ring-amber-400/25 bg-amber-400/10" },
} as const;

export default function KpiTile({ label, value, hint, icon: Icon, tone = "default", bar }: KpiTileProps) {
  const tones = TONE_CLASSES[tone];
  const fraction = bar ? Math.min(1, Math.max(0, bar.fraction)) : null;

  return (
    <div className="flex min-w-0 flex-col gap-2 rounded-xl border border-white/10 bg-zinc-950/70 px-3.5 py-3">
      <div className="flex items-center gap-2.5">
        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset ${tones.ring}`}>
          <Icon className={`h-4 w-4 ${tones.icon}`} aria-hidden="true" />
        </span>
        <p className="truncate text-[11px] font-medium uppercase tracking-[0.14em] text-zinc-500">{label}</p>
      </div>
      <p className="font-display text-2xl font-semibold tracking-tight text-zinc-50">{value}</p>
      {fraction !== null ? (
        <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
          <div className="h-full rounded-full bg-emerald-500/70" style={{ width: `${fraction * 100}%` }} />
        </div>
      ) : null}
      {hint ? <p className="truncate text-[11px] text-zinc-500">{hint}</p> : null}
    </div>
  );
}
