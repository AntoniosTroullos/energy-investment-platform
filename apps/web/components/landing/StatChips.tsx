"use client";

import { motion } from "motion/react";

const STATS = [
  { value: "718", label: "Candidate sites screened" },
  { value: "485", label: "Substations mapped" },
  { value: "949", label: "Transmission lines" },
  { value: "13", label: "Regions covered" },
];

export default function StatChips() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {STATS.map((stat, index) => (
        <motion.div
          key={stat.label}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 + index * 0.08, duration: 0.4 }}
          className="rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-center backdrop-blur-sm"
        >
          <p className="font-display text-xl font-semibold text-emerald-300">{stat.value}</p>
          <p className="mt-1 text-[11px] leading-tight text-zinc-500">{stat.label}</p>
        </motion.div>
      ))}
    </div>
  );
}
