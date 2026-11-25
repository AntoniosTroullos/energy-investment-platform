import type { ReactNode } from "react";

// The one surface every dashboard panel sits on, so twelve panels cannot
// drift into twelve slightly different cards. Matches the app's existing
// panels: zinc-950 over the page's grid background, a hairline white border,
// and a monospace eyebrow heading.

type DashboardCardProps = {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
};

export default function DashboardCard({
  title,
  subtitle,
  action,
  className = "",
  bodyClassName = "",
  children,
}: DashboardCardProps) {
  return (
    <section
      className={`flex flex-col overflow-hidden rounded-2xl border border-white/10 bg-zinc-950/70 shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_18px_40px_-28px_rgba(0,0,0,0.9)] backdrop-blur-sm ${className}`}
    >
      <header className="flex items-start justify-between gap-3 border-b border-white/5 px-4 py-3">
        <div className="min-w-0">
          <h2 className="font-display text-[13px] font-semibold tracking-tight text-zinc-100">{title}</h2>
          {subtitle ? <p className="mt-0.5 truncate text-[11px] text-zinc-500">{subtitle}</p> : null}
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </header>
      <div className={`flex-1 px-4 py-3 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
