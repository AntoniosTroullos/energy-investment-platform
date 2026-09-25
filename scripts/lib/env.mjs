// Shared helpers for the repo-level dev/doctor/test scripts. Node built-ins
// only, so `node scripts/dev.mjs` works on a fresh checkout with no install.

import { spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

export const isWindows = process.platform === "win32";
export const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const apiDir = path.join(repoRoot, "apps", "api");
export const webDir = path.join(repoRoot, "apps", "web");
export const nextBin = path.join(webDir, "node_modules", "next", "dist", "bin", "next");

export const DEFAULT_API_PORT = 8000;
export const DEFAULT_WEB_PORT = 3000;

const useColor = process.stdout.isTTY && !process.env.NO_COLOR;
const paint = (code) => (text) => (useColor ? `[${code}m${text}[0m` : text);
export const color = {
  dim: paint("2"),
  red: paint("31"),
  green: paint("32"),
  yellow: paint("33"),
  cyan: paint("36"),
  magenta: paint("35"),
  bold: paint("1"),
};

/** Interpreter for apps/api: API_PYTHON override, else its own .venv. */
export function resolveApiPython() {
  const override = process.env.API_PYTHON?.trim();
  if (override) return existsSync(override) ? override : null;

  const venvPython = isWindows
    ? path.join(apiDir, ".venv", "Scripts", "python.exe")
    : path.join(apiDir, ".venv", "bin", "python");
  return existsSync(venvPython) ? venvPython : null;
}

export const API_VENV_HELP = [
  "apps/api has no virtualenv. Create one with:",
  isWindows
    ? "  python -m venv apps\\api\\.venv && apps\\api\\.venv\\Scripts\\python -m pip install -r apps\\api\\requirements.txt"
    : "  python3 -m venv apps/api/.venv && apps/api/.venv/bin/python -m pip install -r apps/api/requirements.txt",
  "(or point API_PYTHON at an interpreter that already has the requirements)",
].join("\n");

/**
 * The Next dev server that owns apps/web's default build directory, if one is
 * alive. Next writes {pid, port, appUrl, ...} to .next/dev/lock and refuses to
 * start a second dev server against the same directory.
 */
export function readRunningNextDev() {
  try {
    const lock = JSON.parse(readFileSync(path.join(webDir, ".next", "dev", "lock"), "utf8"));
    if (!Number.isInteger(lock.pid)) return null;
    process.kill(lock.pid, 0); // throws if the process is gone (stale lock)
    return { pid: lock.pid, port: lock.port, appUrl: lock.appUrl };
  } catch {
    return null;
  }
}

export function isPortInUse(port, host = "127.0.0.1", timeoutMs = 600) {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host });
    const finish = (inUse) => {
      socket.destroy();
      resolve(inUse);
    };
    socket.setTimeout(timeoutMs, () => finish(false));
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
  });
}

export async function httpOk(url, timeoutMs = 3000) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
    return response.ok;
  } catch {
    return false;
  }
}

export async function waitFor(check, { timeoutMs, intervalMs = 500 }) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await check()) return true;
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  return false;
}

/** Forwards a child's output line by line with a coloured [tag] prefix. */
export function pipeWithPrefix(stream, tag, paintTag) {
  let buffered = "";
  stream.setEncoding("utf8");
  stream.on("data", (chunk) => {
    buffered += chunk;
    const lines = buffered.split(/\r?\n/);
    buffered = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim()) console.log(`${paintTag(`[${tag}]`)} ${line}`);
    }
  });
  stream.on("end", () => {
    if (buffered.trim()) console.log(`${paintTag(`[${tag}]`)} ${buffered}`);
  });
}

/** Kills a child and everything it spawned (uvicorn --reload and next both fork). */
export function killTree(child) {
  if (!child || child.exitCode !== null || child.pid === undefined) return;
  if (isWindows) {
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    child.kill("SIGTERM");
  }
}

/** Runs a command to completion, streaming its output; resolves with its exit code. */
export function runToCompletion(command, args, { cwd, env, tag, paintTag = (text) => text, shell = false } = {}) {
  return new Promise((resolve) => {
    // shell: true is only for a single command string (e.g. `npm ...`, which is
    // npm.cmd on Windows); passing an args array with a shell is deprecated.
    const child = spawn(command, args, {
      cwd,
      env: { ...process.env, ...env },
      stdio: ["ignore", "pipe", "pipe"],
      shell,
    });
    if (tag) {
      pipeWithPrefix(child.stdout, tag, paintTag);
      pipeWithPrefix(child.stderr, tag, paintTag);
    } else {
      child.stdout.pipe(process.stdout);
      child.stderr.pipe(process.stderr);
    }
    child.on("error", (error) => {
      console.error(color.red(`Could not start ${command}: ${error.message}`));
      resolve(1);
    });
    child.on("close", (code) => resolve(code ?? 1));
  });
}

/** Tiny --flag / --key value / --key=value parser (no dependency). */
export function parseArgs(argv, { booleans = [], values = [] }) {
  const parsed = {};
  for (let index = 0; index < argv.length; index += 1) {
    const raw = argv[index];
    if (!raw.startsWith("--")) throw new Error(`Unexpected argument: ${raw}`);

    const [name, inline] = raw.slice(2).split("=", 2);
    if (booleans.includes(name)) {
      parsed[name] = true;
    } else if (values.includes(name)) {
      const value = inline ?? argv[++index];
      if (value === undefined) throw new Error(`--${name} needs a value`);
      parsed[name] = value;
    } else {
      throw new Error(`Unknown option: --${name}`);
    }
  }
  return parsed;
}

export function parsePort(value, fallback, flag) {
  if (value === undefined) return fallback;
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`--${flag} must be a port number between 1 and 65535 (got "${value}")`);
  }
  return port;
}
