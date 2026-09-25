import type { Staleness } from "../lib/pypsaScenario/pypsaScenario.types";

const REASON_LABELS: Record<Staleness["reasons"][number]["code"], string> = {
  model_code_changed: "Model code changed",
  model_inputs_changed: "Model inputs changed",
  parent_resolved: "Electricity case re-solved",
};

function formatDate(iso: string | null): string {
  if (!iso) {
    return "unknown time";
  }
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "unknown time" : date.toLocaleString();
}

/**
 * Amber "Outdated" pill for a solved result whose model code/inputs (or parent
 * electricity case) changed after it was solved. Renders nothing for a fresh
 * or missing result, so a row without the badge means "nothing has changed
 * since this was solved" -- not "unchecked".
 */
export default function StaleBadge({ staleness }: { staleness: Staleness | null }) {
  if (!staleness || !staleness.is_stale) {
    return null;
  }

  const tooltip = [
    `Solved ${formatDate(staleness.solved_at)}. Re-solve to reflect the current model.`,
    ...staleness.reasons.map(
      (reason) => `• ${REASON_LABELS[reason.code]} (${formatDate(reason.changed_at)}): ${reason.detail}`,
    ),
  ].join("\n");

  return (
    <span
      title={tooltip}
      className="inline-flex shrink-0 cursor-help items-center rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-300"
    >
      Outdated
    </span>
  );
}
