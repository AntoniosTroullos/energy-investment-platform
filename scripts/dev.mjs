#!/usr/bin/env node
// One command to run the whole app: API (FastAPI/uvicorn) + web (Next.js).
//
//   npm run dev                       # api :8000, web :3000
//   npm run dev -- --api-port 8100 --web-port 3100
//   npm run dev -- --reload           # uvicorn auto-reload on Python edits
//   npm run dev -- --api-only | --web-only | --no-warm
//
// What it automates: finds the right interpreter, wires the two halves
// together (CORS origins for the API, NEXT_PUBLIC_API_BASE_URL for the web app)
// for whatever ports you chose, reuses a service that is already healthy on
// its port instead of failing, waits until both answer, warms the slow map
// layers, reports whether PyPSA solving is available, and shuts both down
// cleanly on Ctrl+C.

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";

import {
  API_VENV_HELP,
  DEFAULT_API_PORT,
  DEFAULT_WEB_PORT,
  apiDir,
  color,
  httpOk,
  isPortInUse,
  killTree,
  nextBin,
  parseArgs,
  parsePort,
  pipeWithPrefix,
  readRunningNextDev,
  repoRoot,
  resolveApiPython,
  runToCompletion,
  waitFor,
  webDir,
} from "./lib/env.mjs";

const ALTERNATE_DIST_DIR = ".next-alt";

const log = (message) => console.log(`${color.green("[dev]")} ${message}`);
const warn = (message) => console.log(`${color.yellow("[dev]")} ${message}`);
const fail = (message) => {
  console.error(`${color.red("[dev]")} ${message}`);
  process.exit(1);
};

let options;
try {
  options = parseArgs(process.argv.slice(2), {
    booleans: ["reload", "api-only", "web-only", "no-warm", "help"],
    values: ["api-port", "web-port"],
  });
} catch (error) {
  fail(`${error.message}\nRun with --help for usage.`);
}

if (options.help) {
  console.log(
    [
      "Usage: npm run dev -- [options]",
      "",
      "  --api-port <n>   API port (default 8000)",
      "  --web-port <n>   web port (default 3000)",
      "  --reload         restart the API on Python file changes",
      "  --api-only       only start the API",
      "  --web-only       only start the web app",
      "  --no-warm        skip warming the slow map layers after the API is up",
      "",
      "Env: API_PYTHON (interpreter for apps/api), PYPSA_PROJECT_ROOT, PYPSA_PYTHON,",
      "     API_CORS_ORIGINS (see apps/api/app/settings.py)",
    ].join("\n"),
  );
  process.exit(0);
}

let apiPort;
let webPort;
try {
  apiPort = parsePort(options["api-port"], DEFAULT_API_PORT, "api-port");
  webPort = parsePort(options["web-port"], DEFAULT_WEB_PORT, "web-port");
} catch (error) {
  fail(error.message);
}

if (options["api-only"] && options["web-only"]) fail("--api-only and --web-only cannot be combined.");

const startApi = !options["web-only"];
const startWeb = !options["api-only"];
const apiUrl = `http://127.0.0.1:${apiPort}`;
const webUrl = `http://localhost:${webPort}`;

const children = [];
let shuttingDown = false;

function shutdown(exitCode = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  log("Shutting down...");
  for (const child of children) killTree(child);
  // Give the process trees a moment to release their ports before exiting.
  setTimeout(() => process.exit(exitCode), 400);
}
process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

/** Spawns a long-running service and tears everything down if it dies. */
function launch(tag, paintTag, command, args, { cwd, env }) {
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  children.push(child);
  pipeWithPrefix(child.stdout, tag, paintTag);
  pipeWithPrefix(child.stderr, tag, paintTag);
  child.on("error", (error) => {
    console.error(color.red(`[${tag}] could not start: ${error.message}`));
    shutdown(1);
  });
  child.on("exit", (code) => {
    if (shuttingDown) return;
    console.error(color.red(`[${tag}] exited unexpectedly (code ${code}).`));
    shutdown(code || 1);
  });
  return child;
}

async function ensureFree(port, healthUrl, label) {
  if (!(await isPortInUse(port))) return "start";
  if (await httpOk(healthUrl)) {
    warn(`${label} is already running and healthy on :${port} -- reusing it (not restarted).`);
    return "reuse";
  }
  fail(`Port ${port} is in use by something that is not this app's ${label}. Free it or pick another port.`);
}

async function main() {
  // Every origin the browser may load the web app from must be allowed by the
  // API's CORS policy, and it has to follow --web-port.
  const corsOrigins = process.env.API_CORS_ORIGINS?.trim() || `http://localhost:${webPort},http://127.0.0.1:${webPort}`;

  if (startApi) {
    const python = resolveApiPython();
    if (!python) fail(API_VENV_HELP);

    if ((await ensureFree(apiPort, `${apiUrl}/health`, "API")) === "start") {
      const args = ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(apiPort)];
      if (options.reload) args.push("--reload");
      log(`Starting API on ${apiUrl}${options.reload ? " (auto-reload)" : ""}`);
      launch("api", color.cyan, python, args, { cwd: apiDir, env: { API_CORS_ORIGINS: corsOrigins } });
    }
  }

  if (startWeb) {
    if (!existsSync(nextBin)) {
      log("apps/web/node_modules is missing -- running npm install (one-time)...");
      const code = await runToCompletion("npm --prefix apps/web install", [], {
        cwd: repoRoot,
        tag: "npm",
        paintTag: color.dim,
        shell: true,
      });
      if (code !== 0 || !existsSync(nextBin)) fail("npm install failed; fix that and re-run.");
    }

    if ((await ensureFree(webPort, webUrl, "web app")) === "start") {
      // Next permits one dev server per build directory. If another instance
      // (say, started from a different terminal) already holds the default
      // one on a different port, give this instance the fixed alternate
      // directory so both can run side by side instead of this one crashing
      // on start. It is one fixed name (not per-port) because Next adds every
      // new distDir to tsconfig.json's "include"; .next-alt is registered
      // there once, so the launcher never rewrites that file.
      const other = readRunningNextDev();
      const distDir = other ? ALTERNATE_DIST_DIR : undefined;
      if (other) {
        warn(`Another Next dev server (PID ${other.pid}) is running on ${other.appUrl}; using a separate build directory (${distDir}) for this one.`);
      }
      log(`Starting web app on ${webUrl} (API -> ${apiUrl})`);
      launch("web", color.magenta, process.execPath, [nextBin, "dev", "--port", String(webPort)], {
        cwd: webDir,
        env: { NEXT_PUBLIC_API_BASE_URL: apiUrl, ...(distDir ? { NEXT_DIST_DIR: distDir } : {}) },
      });
    } else if (apiPort !== DEFAULT_API_PORT) {
      warn(`The reused web app was started elsewhere and may still point at the default API port ${DEFAULT_API_PORT}.`);
    }
  }

  if (startApi) {
    const apiUp = await waitFor(() => httpOk(`${apiUrl}/health`), { timeoutMs: 90_000 });
    if (!apiUp) fail(`API did not answer on ${apiUrl}/health within 90s.`);
    log(color.green(`API ready:  ${apiUrl}   (docs: ${apiUrl}/docs)`));
    await reportBridge();
    if (!options["no-warm"]) void warmSlowLayers();
  }

  if (startWeb) {
    const webUp = await waitFor(() => httpOk(webUrl), { timeoutMs: 120_000, intervalMs: 1000 });
    if (!webUp) fail(`Web app did not answer on ${webUrl} within 120s.`);
    log(color.green(`Web ready:  ${webUrl}   (Scenario Studio: ${webUrl}/scenarios)`));
  }

  log(color.dim("Ctrl+C stops everything that this command started."));
}

async function reportBridge() {
  try {
    const response = await fetch(`${apiUrl}/system/status`, { signal: AbortSignal.timeout(10_000) });
    const status = await response.json();
    if (status.bridge?.ready) {
      const years = status.bridge.solved_electricity_years.join(", ") || "none yet";
      log(`PyPSA solving: ${color.green("available")} (solved electricity years: ${years})`);
    } else {
      warn(
        `PyPSA solving: ${color.yellow("unavailable")} -- missing: ${status.bridge?.missing?.join(", ")}. ` +
          "Everything else works; run `npm run doctor` for details.",
      );
    }
    if (!status.data?.ready) {
      warn("Some map data layers are missing -- run `npm run doctor` for the list.");
    }
  } catch {
    warn("Could not read /system/status (older API build?) -- skipping the PyPSA check.");
  }
}

// The first request for each heavy layer pays a multi-second load + geographic
// filter (see apps/api/app/generators.py); doing it now means the first browser
// visit is not the one that waits.
async function warmSlowLayers() {
  const started = Date.now();
  await Promise.all(
    ["/substations", "/transmission-lines", "/plants"].map((route) =>
      fetch(`${apiUrl}${route}`, { signal: AbortSignal.timeout(180_000) }).then((r) => r.arrayBuffer()).catch(() => undefined),
    ),
  );
  if (!shuttingDown) log(color.dim(`Map layers warmed in ${((Date.now() - started) / 1000).toFixed(1)}s.`));
}

main().catch((error) => fail(error.stack || String(error)));
