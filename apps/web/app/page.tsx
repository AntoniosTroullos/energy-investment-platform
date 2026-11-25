"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, Lock, Mail } from "lucide-react";
import { motion } from "motion/react";

import NetworkTeaser from "../components/landing/NetworkTeaser";
import StatChips from "../components/landing/StatChips";

// This "sign in" is decorative by design -- it's a public demo, so anything
// typed here (or nothing at all) leads straight into the app. No backend
// auth exists for it, intentionally.
export default function LandingPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <main className="relative flex min-h-screen flex-col overflow-hidden text-zinc-100">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(circle at 15% 10%, rgba(34,184,145,0.12), transparent 45%), radial-gradient(circle at 85% 85%, rgba(34,184,145,0.08), transparent 50%)",
        }}
      />

      <header className="relative z-10 flex items-center gap-3 px-6 py-6 sm:px-10">
        <svg viewBox="0 0 24 24" aria-hidden="true" className="h-6 w-6 text-emerald-400">
          <path
            d="M13 2 4 13.2h6.2L10.6 22 20 9.6h-6.4L13 2Z"
            fill="currentColor"
            fillOpacity="0.9"
          />
        </svg>
        <p className="font-display text-sm tracking-tight text-zinc-100">Energy Investment Platform</p>
      </header>

      <div className="relative z-10 flex flex-1 flex-col items-center justify-center gap-14 px-6 py-10 sm:px-10 lg:flex-row lg:items-center lg:gap-20">
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="order-2 flex w-full max-w-md flex-col items-center gap-8 lg:order-1 lg:items-start"
        >
          <NetworkTeaser />
          <div className="w-full max-w-sm">
            <StatChips />
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5 }}
          className="order-1 w-full max-w-md lg:order-2"
        >
          <div className="rounded-2xl border border-white/10 bg-zinc-950/60 p-8 shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_24px_60px_-20px_rgba(0,0,0,0.6)] backdrop-blur-xl">
            <p className="font-display text-2xl font-semibold tracking-tight text-zinc-50">
              Screen Greece&rsquo;s grid for your next site
            </p>
            <p className="mt-2 text-sm text-zinc-400">
              Scenario-based investment screening and PyPSA energy modelling, built on real
              infrastructure data.
            </p>

            <form
              className="mt-8 flex flex-col gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                router.push("/overview");
              }}
            >
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">Email</span>
                <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2.5 transition focus-within:border-emerald-500/40 focus-within:ring-1 focus-within:ring-emerald-500/30">
                  <Mail className="h-4 w-4 text-zinc-500" />
                  <input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    autoComplete="off"
                    className="w-full bg-transparent text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none"
                  />
                </div>
              </label>

              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-zinc-500">Password</span>
                <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2.5 transition focus-within:border-emerald-500/40 focus-within:ring-1 focus-within:ring-emerald-500/30">
                  <Lock className="h-4 w-4 text-zinc-500" />
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="••••••••"
                    autoComplete="off"
                    className="w-full bg-transparent text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none"
                  />
                </div>
              </label>

              <motion.button
                type="submit"
                whileTap={{ scale: 0.98 }}
                className="mt-2 flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-zinc-950 transition hover:bg-emerald-400"
              >
                Sign In
                <ArrowRight className="h-4 w-4" />
              </motion.button>
            </form>

            <div className="mt-6 flex items-center gap-3 text-xs text-zinc-600">
              <div className="h-px flex-1 bg-white/10" />
              or
              <div className="h-px flex-1 bg-white/10" />
            </div>

            <button
              type="button"
              onClick={() => router.push("/overview")}
              className="mt-4 w-full rounded-lg border border-white/10 px-4 py-2.5 text-sm font-medium text-zinc-300 transition hover:border-emerald-500/30 hover:bg-white/5 hover:text-zinc-100"
            >
              Continue as Guest
            </button>

            <p className="mt-6 text-center text-xs text-zinc-600">
              This is a public live demo — no account is required or stored. Any input, or none at
              all, takes you straight in.
            </p>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
