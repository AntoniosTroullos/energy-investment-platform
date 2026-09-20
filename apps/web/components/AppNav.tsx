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
    <header className="flex h-14 w-full shrink-0 items-center justify-between border-b border-white/10 bg-zinc-900 px-6">
      <p className="text-sm font-semibold tracking-tight text-zinc-100">
        Energy Investment Platform
      </p>
      <nav className="flex items-center gap-2">
        {NAV_LINKS.map((link) => {
          const isActive = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);

          return (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                isActive
                  ? "bg-emerald-500/10 text-emerald-300"
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
