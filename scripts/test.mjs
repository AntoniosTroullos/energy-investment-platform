#!/usr/bin/env node
// `npm test` -- runs every automated check in one go: the API's unittest suite,
// then the web app's type-check and lint. Each stage prints its own output and
// a final summary, and the exit code is non-zero if any stage failed.
//   npm test              everything
//   npm run test:api      API tests only
//   npm run test:web      web type-check + lint only

import { existsSync } from "node:fs";
import path from "node:path";

import {
  API_VENV_HELP,
  apiDir,
  color,
  nextBin,
  parseArgs,
  resolveApiPython,
  runToCompletion,
  webDir,
} from "./lib/env.mjs";

let options;
try {
  options = parseArgs(process.argv.slice(2), { booleans: ["api", "web"] });
} catch (error) {
  console.error(color.red(error.message));
  process.exit(1);
}

const runApi = options.api || !options.web;
const runWeb = options.web || !options.api;
const results = [];

async function stage(name, command, args, opts) {
  console.log(`\n${color.bold(`== ${name}`)}`);
  const code = await runToCompletion(command, args, opts);
  results.push({ name, ok: code === 0 });
}

if (runApi) {
  const python = resolveApiPython();
  if (!python) {
    console.error(color.red(API_VENV_HELP));
    results.push({ name: "API tests", ok: false });
  } else {
    await stage("API tests (unittest)", python, ["-m", "unittest", "discover", "-s", "tests"], { cwd: apiDir });
  }
}

if (runWeb) {
  if (!existsSync(nextBin)) {
    console.error(color.red("apps/web dependencies missing: npm --prefix apps/web install"));
    results.push({ name: "Web checks", ok: false });
  } else {
    // Run the tools' JS entry points with the current node: no .cmd shims, so
    // the same code path works on Windows and POSIX.
    const tsc = path.join(webDir, "node_modules", "typescript", "bin", "tsc");
    const eslint = path.join(webDir, "node_modules", "eslint", "bin", "eslint.js");
    await stage("Web type-check (tsc --noEmit)", process.execPath, [tsc, "--noEmit"], { cwd: webDir });
    await stage("Web lint (eslint)", process.execPath, [eslint, "app", "components", "lib"], { cwd: webDir });
  }
}

console.log(`\n${color.bold("Summary")}`);
for (const { name, ok } of results) console.log(`  ${ok ? color.green("[ok]") : color.red("[!!]")} ${name}`);
process.exit(results.every((r) => r.ok) ? 0 : 1);
