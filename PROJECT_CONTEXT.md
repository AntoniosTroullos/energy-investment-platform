# Project Context

## Project name
Energy Investment Platform

## What this app is
A map-based energy investment intelligence platform built as a beginner-friendly product prototype.

The goal is to evolve it step by step from:
1. an infrastructure viewer,
2. to an investment screening tool,
3. to a decision-support tool,
4. and later into an optimization and LLM-assisted scenario platform.

---

## Current tech stack
### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- MapLibre GL JS

### Current data mode
- Local mock data only
- No backend yet
- No database yet
- No optimization backend yet
- No LLM integration yet

---

## Current product capabilities
The app currently includes:

- interactive map
- left sidebar
- right-side details drawer
- layer toggles
- grouped layer controls
- asset search with zoom/focus
- candidate investment cells
- calculated investment scores
- analysis filters
- Top Opportunities panel
- compare mode for candidate cells
- recommendation summary
- scenario controls
- structured Scenario object
- scenario debug JSON view

---

## Current product purpose
Right now the app is in the **investment screening and decision-support prototype** stage.

It is not yet:
- a real backend-driven GIS platform
- a validated network model
- a true optimization engine
- an LLM-driven scenario platform

That will come later.

---

## Main architecture direction
We are building the platform in layers:

1. **Infrastructure Viewer**
   - map
   - layers
   - search
   - feature selection
   - details drawer

2. **Investment Screening Tool**
   - candidate cells
   - calculated scores
   - filters
   - Top Opportunities
   - comparison
   - recommendation summary

3. **Scenario Layer**
   - user-defined scenario controls
   - structured Scenario object
   - scenario debug view

4. **Future Backend Layer**
   - FastAPI
   - real geospatial datasets
   - API endpoints
   - PostGIS later

5. **Future Optimization Layer**
   - PyPSA and/or Pyomo
   - siting and investment logic
   - grid constraints
   - budget and policy constraints

6. **Future LLM Layer**
   - user writes natural-language constraints
   - app converts them into a validated structured scenario
   - optimization runs from that structured scenario

---

## Current working principles
These rules are important:

- keep the code beginner-readable
- do not overengineer
- preserve the existing UI unless explicitly asked to redesign it
- prefer small clear components
- prefer explicit logic over clever abstractions
- do not add backend unless explicitly requested
- do not add optimization yet unless explicitly requested
- do not add LLM logic yet unless explicitly requested
- keep the app stable while adding features incrementally

---

## Current scenario model
The app should use a structured Scenario object rather than scattered independent state values.

Current Scenario fields should include at least:
- budgetTier
- preferredTechnology
- maxConnectionDistanceKm
- excludeLandConstrained
- minInvestmentScore

This Scenario object is intended to become the future bridge to:
- backend APIs
- saved scenarios
- optimization inputs
- LLM-generated model inputs

---

## Current candidate cell philosophy
Suitability / candidate cells are not real infrastructure assets.

They are **analysis outputs** representing candidate investment areas.

Each candidate cell should carry properties like:
- technology
- solar_score
- wind_score
- distance_to_substation_km
- distance_to_line_km
- land_excluded
- connection_cost_level
- investment_score

The investment score should be calculated from the other fields, not manually hardcoded.

---

## What should not be assumed yet
Do not assume the current transmission lines, plants, and substations form a real validated electrical topology.

At this stage:
- infrastructure is still mock/local
- visual layers are not yet a true network model
- missing or imperfect connections may simply be mock data limitations

---

## Current UI philosophy
The app should feel like a professional geospatial decision-support product.

Important UX principles:
- map-first
- clean left control panel
- clean right details drawer
- visible reasoning
- readable filters
- ranked opportunities
- explainable recommendations

---

## Current development priority
We are following this sequence:

1. finish the frontend decision workflow
2. stabilize scenario structure
3. add save/load scenario presets
4. introduce backend only after the frontend workflow is solid
5. replace mock data with more realistic data
6. add optimization
7. add LLM scenario translation last

---

## What Codex should do before major edits
Before changing code for a major task:

1. inspect the relevant files
2. summarize the current implementation briefly
3. preserve working behavior unless the requested task changes it
4. make the requested change only
5. explain which files changed and why

---

## Near-term roadmap
The next likely steps are:

- save/load preset scenarios
- cleaner result ranking UX
- richer candidate score explanation
- more realistic candidate filtering
- one new contextual layer or infrastructure layer
- backend introduction later

---

## Long-term vision
The final vision is:

A map-based energy intelligence platform that:
- visualizes infrastructure,
- scores candidate opportunities,
- compares and recommends investment options,
- accepts structured or natural-language scenarios,
- and eventually runs real optimization for renewable, grid, and broader energy investment decisions.
