"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_LINKS = [
  { href: "/", label: "Map" },
  { href: "/scenarios", label: "Scenario Studio" },
] as const;

export default function AppNav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 flex h-16 w-full shrink-0 items-center justify-between border-b border-white/10 bg-zinc-950/80 px-6 backdrop-blur-md print:hidden">
      <div className="flex items-center gap-3">
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          className="h-6 w-6 text-emerald-400"
        >
          <path
            d="M13 2 4 13.2h6.2L10.6 22 20 9.6h-6.4L13 2Z"
            fill="currentColor"
            fillOpacity="0.9"
          />
        </svg>
        <p className="font-display text-sm tracking-tight text-zinc-100">
          Energy Investment Platform
        </p>
      </div>
      <nav className="flex items-center gap-1">
        {NAV_LINKS.map((link) => {
          const isActive = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);

          return (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded-lg px-3.5 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-emerald-500/10 text-emerald-300 ring-1 ring-inset ring-emerald-500/30"
                  : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
