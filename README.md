# Energy Investment Platform

Map-based energy intelligence for Greece: an infrastructure explorer, investment
screening, and a Scenario Studio that runs real PyPSA optimisation models.

```
apps/web   Next.js 16 + MapLibre + Recharts   (the UI)
apps/api   FastAPI                            (data layers, screening, PyPSA bridge)
scripts/   repo-level dev / doctor / test commands
data/, src/, scripts/*.py   offline data-prep for national load (not needed to run the app)
```

## Quick start

Requires Node 20+ and Python 3.10+ (developed on 3.14).

```bash
# one-time: API environment
python -m venv apps/api/.venv
apps/api/.venv/Scripts/python -m pip install -r apps/api/requirements.txt   # POSIX: apps/api/.venv/bin/python

# every time
npm run dev
```

`npm run dev` installs the web dependencies if they are missing, starts the API
on <http://127.0.0.1:8000> and the web app on <http://localhost:3000>, waits until
both answer, warms the slow map layers, and tells you whether PyPSA solving is
available. Ctrl+C stops what it started.

If something is off, run `npm run doctor` — it says what is missing and how to fix it.

## Commands

| Command | What it does |
| --- | --- |
| `npm run dev` | API + web together (`-- --reload` for API auto-reload) |
| `npm run dev:api` / `npm run dev:web` | just one half |
| `npm run doctor` | check tooling, the API environment, data layers, the PyPSA bridge and ports |
| `npm run doctor:deep` | also import the whole solver stack in the solver interpreter (about a minute) |
| `npm test` | API unit tests, then web type-check and lint |
| `npm run test:api` / `npm run test:web` | one side only |

Useful flags: `npm run dev -- --api-port 8100 --web-port 3100`. The launcher wires the
two halves for whatever ports you pick (CORS on the API, the API URL in the web app).
If a service is already healthy on its port it is reused, not restarted. If another
Next dev server for this project is already running on a different port, the new one
gets its own build directory (`.next-alt`) so both can run side by side.

## Configuration

Everything has a working default; set these only to override.

| Variable | Read by | Meaning | Default |
| --- | --- | --- | --- |
| `PYPSA_PROJECT_ROOT` | API | root of the sibling project that owns the scenario scripts | `~/PycharmProjects/pythonProject1` |
| `PYPSA_PYTHON` | API | interpreter used to run those scripts | `<root>/pypsa-greece/.venv314/Scripts/python.exe` |
| `API_CORS_ORIGINS` | API | comma-separated browser origins allowed to call the API | `http://localhost:3000,http://127.0.0.1:3000` |
| `NEXT_PUBLIC_API_BASE_URL` | web | where the browser finds the API (restart `next dev` after changing) | `http://127.0.0.1:8000` |
| `API_PYTHON` | scripts | interpreter for `apps/api` | `apps/api/.venv` |

The API resolves its settings in `apps/api/app/settings.py`; the web app reads its URL in
`apps/web/lib/config.ts`. Copy `apps/web/.env.example` to `apps/web/.env.local` to persist a web override.

## The PyPSA bridge

Scenario Studio solves real PyPSA models, but that code lives in a separate project
(`PYPSA_PROJECT_ROOT`) with its own Python environment. The API runs its scripts as
subprocesses and reads the result files back, so `apps/api` stays free of
pandas/pypsa/linopy/highspy/xgboost. Only one of that project's environments
(`pypsa-greece/.venv314`) can import the whole stack, which is why the default is pinned to it.

`GET /system/status` (and `npm run doctor`) reports whether the bridge is ready. When it is
not, everything except solving still works.

## Tests

`npm test` runs the API `unittest` suite (some modules load the full merged plant feed and take
about half a minute), then `tsc --noEmit` and `eslint` for the web app.
