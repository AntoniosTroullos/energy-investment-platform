#!/usr/bin/env node
// `npm run doctor` -- verifies everything the app needs and says what to fix.
//   npm run doctor            fast file/port checks
//   npm run doctor -- --deep  also imports the whole PyPSA solver stack (~1 min)
//
// Exit code 1 only for problems that stop the app itself (Node, dependencies,
// the API environment, missing map data). PyPSA solving being unavailable is a
// warning: the map and screening views work without it.

import { existsSync } from "node:fs";

import {
  API_VENV_HELP,
  DEFAULT_API_PORT,
  DEFAULT_WEB_PORT,
  apiDir,
  color,
  httpOk,
  isPortInUse,
  nextBin,
  parseArgs,
  resolveApiPython,
  runToCompletion,
} from "./lib/env.mjs";

let options;
try {
  options = parseArgs(process.argv.slice(2), { booleans: ["deep", "strict", "help"] });
} catch (error) {
  console.error(color.red(error.message));
  process.exit(1);
}
if (options.help) {
  console.log("Usage: npm run doctor -- [--deep] [--strict]\n  --deep    import the solver stack too (slow)\n  --strict  exit 1 when PyPSA solving is unavailable, too");
  process.exit(0);
}

let problems = 0;
const ok = (message) => console.log(`  ${color.green("[ok]")} ${message}`);
const bad = (message, hint) => {
  problems += 1;
  console.log(`  ${color.red("[!!]")} ${message}`);
  if (hint) for (const line of hint.split("\n")) console.log(`       ${color.dim(line)}`);
};
const section = (title) => console.log(`\n${color.bold(title)}`);

section("Tooling");
const nodeMajor = Number(process.versions.node.split(".")[0]);
if (nodeMajor >= 20) ok(`Node ${process.versions.node}`);
else bad(`Node ${process.versions.node} is too old`, "Install Node 20 or newer (Next.js 16 requirement).");

if (existsSync(nextBin)) ok("apps/web dependencies installed");
else bad("apps/web dependencies missing", "Run: npm --prefix apps/web install   (or just `npm run dev`, which does it)");

section("API environment (apps/api)");
const python = resolveApiPython();
if (!python) {
  bad("No interpreter for apps/api", API_VENV_HELP);
} else {
  ok(`Interpreter: ${python}`);
  const code = await runToCompletion(python, ["-c", "import fastapi, uvicorn, pydantic, shapely"], { cwd: apiDir });
  if (code === 0) ok("Required packages import (fastapi, uvicorn, pydantic, shapely)");
  else bad("Required packages are missing", "Run: <api python> -m pip install -r apps/api/requirements.txt");
}

section("Data layers and PyPSA bridge");
if (python) {
  const args = ["-m", "app.system_status"];
  if (options.deep) args.push("--deep");
  if (options.strict) args.push("--strict");
  // The report is printed by the same code the API's /system/status uses, so
  // the CLI and the UI can never disagree about what is configured.
  const code = await runToCompletion(python, args, { cwd: apiDir });
  if (code !== 0) {
    problems += 1;
    console.log(`  ${color.red("[!!]")} ${options.strict ? "Data layers or PyPSA bridge" : "Data layers"} not ready (see above).`);
  }
} else {
  console.log(color.dim("  skipped (no API interpreter)"));
}

section("Ports");
for (const [label, port, path] of [
  ["API", DEFAULT_API_PORT, "/health"],
  ["Web", DEFAULT_WEB_PORT, ""],
]) {
  if (!(await isPortInUse(port))) {
    console.log(`  ${color.dim("[--]")} ${label} :${port} is free`);
  } else if (await httpOk(`http://127.0.0.1:${port}${path}`)) {
    ok(`${label} :${port} is running and healthy`);
  } else {
    console.log(`  ${color.yellow("[??]")} ${label} :${port} is in use by something that did not answer as this app`);
  }
}

section("Overrides in effect");
const overrides = ["API_PYTHON", "PYPSA_PROJECT_ROOT", "PYPSA_PYTHON", "API_CORS_ORIGINS", "NEXT_PUBLIC_API_BASE_URL"];
const active = overrides.filter((name) => process.env[name]?.trim());
if (active.length === 0) console.log(color.dim("  none (all defaults)"));
for (const name of active) console.log(`  ${name}=${process.env[name]}`);

console.log("");
if (problems === 0) {
  console.log(color.green("All required checks passed."));
} else {
  console.log(color.red(`${problems} problem${problems === 1 ? "" : "s"} need attention.`));
  process.exit(1);
}
