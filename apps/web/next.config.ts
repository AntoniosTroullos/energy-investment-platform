import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next allows only one dev server per build directory. `npm run dev` sets
  // NEXT_DIST_DIR (to .next-<port>) when it has to start a second instance
  // next to one that is already running, so parallel instances don't collide.
  distDir: process.env.NEXT_DIST_DIR?.trim() || ".next",
};

export default nextConfig;
