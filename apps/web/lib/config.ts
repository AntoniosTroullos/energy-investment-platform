// Single source of truth for where the FastAPI backend lives.
//
// NEXT_PUBLIC_API_BASE_URL is inlined into the browser bundle at build/dev
// start, so changing it needs a restart of the Next.js server (the `npm run
// dev` launcher at the repo root sets it for you when the API port changes).
// The default matches `uvicorn app.main:app --port 8000` on the local machine.
const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
).replace(/\/+$/, "");

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
