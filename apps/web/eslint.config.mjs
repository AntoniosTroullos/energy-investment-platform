import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // NEXT_DIST_DIR (scripts/dev.mjs --reload) builds a second dev server
    // into .next-alt/ so it doesn't collide with one already running.
    ".next-alt/**",
  ]),
]);

export default eslintConfig;
