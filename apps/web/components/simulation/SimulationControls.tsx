"use client";

import type { ReactNode } from "react";

// The input primitives the three simulator forms share, so a number field
// looks and behaves the same whether it is a capacity, an efficiency or a
// contract price.

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium text-zinc-300">{label}</span>
      {children}
      {hint ? <span className="text-[10px] leading-4 text-zinc-500">{hint}</span> : null}
    </label>
  );
}

export function NumberInput({
  value,
  onChange,
  min,
  max,
  step = 1,
  suffix,
}: {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
}) {
  return (
    <span className="flex items-center gap-2 rounded-lg border border-white/10 bg-zinc-950 px-2.5 py-1.5 focus-within:border-emerald-400">
      <input
        type="number"
        value={Number.isFinite(value) ? value : ""}
        min={min}
        max={max}
        step={step}
        onChange={(event) => {
          const parsed = Number(event.target.value);
          if (Number.isFinite(parsed)) onChange(parsed);
        }}
        className="w-full bg-transparent font-mono text-xs text-zinc-100 outline-none"
      />
      {suffix ? <span className="shrink-0 text-[10px] text-zinc-500">{suffix}</span> : null}
    </span>
  );
}

export function Choice<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          onClick={() => onChange(option.id)}
          className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors ${
            option.id === value
              ? "bg-emerald-500/10 text-emerald-300 ring-1 ring-inset ring-emerald-500/30"
              : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
          }`}
        >
          {option.label}
        </button>
      ))}
    </span>
  );
}

export function Toggle({
  label,
  checked,
  onChange,
  hint,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  hint?: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-2.5">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-emerald-500"
      />
      <span>
        <span className="text-[11px] font-medium text-zinc-300">{label}</span>
        {hint ? <span className="mt-0.5 block text-[10px] leading-4 text-zinc-500">{hint}</span> : null}
      </span>
    </label>
  );
}

export function Metric({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "positive" | "negative";
}) {
  const toneClass =
    tone === "positive" ? "text-emerald-300" : tone === "negative" ? "text-rose-300" : "text-zinc-50";
  return (
    <div className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
      <p className="text-[10px] uppercase tracking-[0.14em] text-zinc-500">{label}</p>
      <p className={`font-display text-lg ${toneClass}`}>{value}</p>
      {hint ? <p className="text-[10px] text-zinc-500">{hint}</p> : null}
    </div>
  );
}

export function formatEur(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  const absolute = Math.abs(value);
  if (absolute >= 1_000_000_000) return `€${(value / 1_000_000_000).toFixed(2)}bn`;
  if (absolute >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}m`;
  if (absolute >= 1_000) return `€${(value / 1_000).toFixed(0)}k`;
  return `€${value.toFixed(digits)}`;
}

export function formatPct(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? "—" : `${value.toFixed(digits)}%`;
}
