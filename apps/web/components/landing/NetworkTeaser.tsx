"use client";

// A stylised, animated stand-in for "the live grid" on the landing page --
// pulsing nodes and flowing connections suggest the real map/data beneath
// without the cost of loading MapLibre + live GeoJSON on a page whose only
// job is to look good before the visitor ever asks for real data.

import { motion } from "motion/react";

type Node = { id: string; x: number; y: number; hub?: boolean };
type Edge = { from: string; to: string };

const NODES: Node[] = [
  { id: "epirus", x: 95, y: 150 },
  { id: "macedonia", x: 150, y: 70 },
  { id: "thrace", x: 260, y: 60 },
  { id: "thessaly", x: 185, y: 150 },
  { id: "central", x: 165, y: 215 },
  { id: "attica", x: 225, y: 230, hub: true },
  { id: "peloponnese", x: 110, y: 285 },
  { id: "aegean", x: 300, y: 160 },
  { id: "cyclades", x: 270, y: 290 },
  { id: "crete", x: 210, y: 360 },
];

const EDGES: Edge[] = [
  { from: "epirus", to: "macedonia" },
  { from: "macedonia", to: "thrace" },
  { from: "macedonia", to: "thessaly" },
  { from: "epirus", to: "thessaly" },
  { from: "thessaly", to: "central" },
  { from: "central", to: "attica" },
  { from: "central", to: "peloponnese" },
  { from: "attica", to: "peloponnese" },
  { from: "attica", to: "aegean" },
  { from: "attica", to: "cyclades" },
  { from: "thrace", to: "aegean" },
  { from: "cyclades", to: "crete" },
];

function nodeById(id: string) {
  return NODES.find((node) => node.id === id)!;
}

export default function NetworkTeaser() {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-md">
      <div
        className="pointer-events-none absolute inset-0 rounded-full blur-3xl"
        style={{
          background:
            "radial-gradient(circle at 56% 58%, rgba(34,184,145,0.35), transparent 60%)",
        }}
      />
      <svg viewBox="0 0 400 400" className="relative h-full w-full">
        {EDGES.map((edge, index) => {
          const from = nodeById(edge.from);
          const to = nodeById(edge.to);
          return (
            <g key={`${edge.from}-${edge.to}`}>
              <line
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="rgba(255,255,255,0.08)"
                strokeWidth={1.5}
              />
              <motion.line
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke="#22b891"
                strokeWidth={1.5}
                strokeDasharray="4 10"
                initial={{ strokeDashoffset: 0, opacity: 0 }}
                animate={{ strokeDashoffset: [0, -28], opacity: [0, 0.8, 0] }}
                transition={{
                  duration: 2.4,
                  repeat: Infinity,
                  delay: index * 0.35,
                  ease: "linear",
                }}
              />
            </g>
          );
        })}

        {NODES.map((node, index) => (
          <g key={node.id}>
            <motion.circle
              cx={node.x}
              cy={node.y}
              r={node.hub ? 10 : 6}
              fill="none"
              stroke="#22b891"
              strokeWidth={1}
              initial={{ opacity: 0.25, scale: 1 }}
              animate={{ opacity: [0.15, 0.5, 0.15], scale: [1, 1.6, 1] }}
              transition={{
                duration: 2.8,
                repeat: Infinity,
                delay: index * 0.22,
                ease: "easeInOut",
              }}
              style={{ transformOrigin: `${node.x}px ${node.y}px` }}
            />
            <circle
              cx={node.x}
              cy={node.y}
              r={node.hub ? 6 : 3.5}
              fill={node.hub ? "#45d2aa" : "#9ca3af"}
            />
          </g>
        ))}
      </svg>
    </div>
  );
}
