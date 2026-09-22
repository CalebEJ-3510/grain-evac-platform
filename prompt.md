# PROMPT.md
## Software Implementation Spec — Smart Grain Stack Evacuation Platform (Software-Only Edition)

> **How to use this file:** this is a build prompt/spec, meant to be handed to a developer or a coding
> agent as the single source of truth for the software implementation. It intentionally does not touch
> hardware. Every physical sensor, radio and lance node from the original architecture is replaced by a
> **synthetic data generation service** that produces realistic, physically-plausible telemetry. Everything
> downstream of that boundary — ingestion, physics inference, risk scoring, dispatch optimization,
> dashboard, alerts — is built exactly as if it were receiving real field data, because from the software's
> point of view it is indistinguishable from the real thing. That boundary is the seam that lets this be a
> 100% software project today and swapped for a real gateway feed later without touching anything above
> Module B.

---

## 0. Non-negotiable constraints

1. **No hardware.** No firmware, no MCU code, no radio protocol implementation, no BOM, no enclosure, no
   energy budget. If a task looks like it's drifting toward "how would the physical node do X" — stop,
   translate it into "how does the simulator emit a value consistent with X."
2. **Synthetic data must be physically honest.** The simulator is not a random number generator with noise
   sprinkled on — it must implement the same sorption thermodynamics the real pipeline expects to invert,
   so that when the gateway pipeline processes the synthetic feed, it recovers moisture values that are
   internally consistent with what the simulator "knows" it generated. This is what makes the demo
   credible to a technical reviewer: feed it a scripted rain event, and the EPI must climb for the right
   reason, on the right stacks, at the right lag.
3. **The frontend must not look, read, or animate like a generated template.** See §8 in full before
   writing a single line of CSS. This is graded as a first-class deliverable, not a wrapper around the
   algorithm.
4. **Every numeric constant in the original design (weights, thresholds, decay constants) is a
   configurable, inspectable value in the running system — never a hardcoded magic number buried in
   business logic.** A reviewer must be able to open a settings/admin view and see exactly what the system
   currently believes, and change it.
5. **The system must be internally explainable.** Every EPI score must be traceable, on demand, back to
   the specific sub-index values and the specific telemetry that produced them. "Because the model said so"
   is not an acceptable end state anywhere in this build.

---

## 1. What this system does (software framing)

A yard holds a variable number of **stacks** (bagged paddy piles). Each stack has 3–6 **sensor nodes**
seeded at different depths/faces. Each node emits an interstitial relative-humidity + temperature reading,
plus a deep-core temperature reading, every simulated 15 minutes. A gateway service ingests this stream,
screens it for faults, inverts a sorption isotherm to estimate grain moisture, tracks its rate of change,
accumulates a mould-risk exposure integral, and fuses all of it with a weather forecast feed. Six weighted
sub-indices are computed per stack and combined into a 0–100 **Evacuation Priority Index (EPI)**. Given a
daily truck capacity, a dispatch optimizer produces a ranked, capacity-constrained loading sequence
respecting yard access precedence. A dashboard renders the yard, the queue, per-stack drill-downs, node
health, and a tiered alert ladder, in a UI built for a yard supervisor standing outdoors on a mid-range
Android phone.

The demo must run **standalone**, generating its own history and its own live stream, so it can be shown to
a reviewer with nothing but a browser tab — no physical dependency, no external API key required to see the
core loop work (a real weather API integration is a bonus layer, not a requirement, see §5.4).

---

## 2. System architecture (4 software modules replacing the original 4 hardware/software modules)

```
┌─────────────────────────┐    ┌──────────────────────────┐    ┌───────────────────────────┐    ┌─────────────────────┐
│ MODULE 1                │    │ MODULE 2                 │    │ MODULE 3                  │    │ MODULE 4             │
│ Synthetic Telemetry      │───▶│ Ingestion & State         │───▶│ EPI Engine & Dispatch      │───▶│ Dashboard & Alerts    │
│ Generator ("the swarm    │    │ Reconstruction            │    │ Optimizer                  │    │ (frontend)            │
│ that doesn't exist")     │    │ ("the gateway")           │    │ ("the brain")              │    │ ("the supervisor's    │
│                          │    │                            │    │                            │    │  window into it")     │
└─────────────────────────┘    └──────────────────────────┘    └───────────────────────────┘    └─────────────────────┘
```

Module 1 replaces the physical lance nodes + LoRa mesh entirely. Modules 2–4 are built exactly as the
original architecture specifies them, because they were never hardware-dependent — they're software that
happened to receive its input from hardware.

---

## 3. Recommended technology stack

Pick a stack that lets one person or a small team ship all four modules without fighting the tools. Suggested
default (swap only with good reason, and record the reason):

- **Backend / simulation / gateway logic:** Python 3.11+, FastAPI for the HTTP + WebSocket layer,
  `asyncio` for the simulation clock, `numpy` + `scipy.stats.theilslopes` for the robust regression,
  Pydantic for every schema in this document (schemas are contracts — enforce them, don't just document
  them).
- **Persistence:** PostgreSQL (or SQLite for local dev/demo — the original spec's "local-first" philosophy
  maps cleanly onto SQLite-by-default, Postgres-in-production). Time-series tables indexed on
  `(stack_id, ts)`.
- **Task/clock engine:** a single internal "simulation clock" service that ticks in configurable
  wall-time-per-simulated-15-minutes, driving both the generator and the gateway recomputation on the same
  heartbeat. Do not let the frontend poll a static JSON file — this needs to feel alive.
- **Live updates:** WebSocket (or Server-Sent Events) push from backend to frontend on every tick, so the
  dashboard visibly updates without a manual refresh — this is the single most important thing for making
  the demo read as a real system rather than a static mockup.
- **Frontend:** React (Vite) + TypeScript. Charting: a small, deliberately chosen library (`visx` or
  `d3` directly) — not a default "drop in Chart.js and accept its look" approach; the sub-index bands, the
  14-day trend lines and the yard plan are custom-drawn SVG, not generic chart-kit output. State:
  React Query (or SWR) for server state, lightweight local state for UI-only concerns. No CSS framework
  that imposes its own visual identity (see §8) — hand-rolled CSS or CSS-in-JS with your own design tokens.
- **i18n:** `react-i18next` or equivalent, English + Tamil from day one (not bolted on later — see §8.7).
- **PWA:** Vite PWA plugin or hand-rolled service worker; the dashboard must be installable and must cache
  the last-synced queue for offline read (§8.8).

---

## 4. Repository structure

```
/backend
  /simulator          — Module 1
    node_model.py
    stack_lifecycle.py
    scenarios.py
    weather_synth.py
    clock.py
  /gateway             — Module 2
    ingest.py
    fault_screening.py
    isotherm.py
    mra.py
    state_record.py
    weather_client.py  — real Open-Meteo client, feature-flagged
  /engine              — Module 3
    sub_indices.py
    epi.py
    dispatch.py
    weights_store.py
  /api                 — Module 4 backend half
    routes/
    ws.py
    schemas.py
  /db
    models.py
    migrations/
  /tests
    test_isotherm.py
    test_mra.py
    test_epi.py
    test_dispatch.py
    test_fault_screening.py
    test_scenarios.py
  main.py
/frontend
  /src
    /design-tokens.ts
    /screens
      YardPlan/
      LoadingQueue/
      StackDetail/
      NodeHealth/
      SeasonReport/
      Settings/
    /components
    /i18n
      en.json
      ta.json
    /lib
      ws-client.ts
      api-client.ts
/docs
  DECISIONS.md         — running log of every design/parameter choice and why
  SCENARIOS.md         — catalogue of the synthetic scenarios and their expected system behaviour
README.md
```

---

## 5. MODULE 1 — Synthetic Telemetry Generator

This is the module that makes the "100% software" framing honest: it must be good enough that a domain
expert watching the resulting dashboard cannot immediately tell it's synthetic.

### 5.1 Entities to model

- **Yard** — a bounding shape (for the yard-plan screen), holding N stacks, one gateway, one weather
  location.
- **Stack** — `stack_id`, tonnage `m_i`, formation date (`age_d` derives from this), row/position (for the
  vulnerability rubric and for precedence), tarpaulin/dunnage/drainage condition (vulnerability rubric
  inputs, §6.5), and 3–6 attached nodes at named positions (`core`, `windward-face`, `leeward-face`,
  `ground-contact`, `crown`).
- **Node** — `node_id`, parent stack, depth/position tag, and an internal **hidden true state**
  (`true_grain_moisture`, `true_water_activity`) that the simulator uses to generate the *observed*
  ERH/temperature it would report — i.e., simulate forward from moisture to RH via the *same* isotherm the
  gateway will later invert, so the round-trip is physically closed. Also holds a `health_state` (`ok`,
  `degrading`, `dead`, `lost`) and `battery_voltage_proxy` (purely cosmetic for the Node Health screen —
  no real energy modelling needed, but it must decay monotonically and realistically over simulated days so
  the node-health screen has something honest to show).

### 5.2 Forward physics model (what the generator computes, before the gateway ever sees it)

For each node, on each 15-minute tick:

1. Advance the node's **true water activity** `a_w` toward a **target equilibrium** driven by:
   - the yard's current/forecast weather (ambient RH, temperature, whether it's raining) — wetting pulls
     `a_w` up, dry/hot conditions pull it down;
   - the node's position (ground-contact and windward nodes react faster and reach higher peak `a_w`
     than crown/interior nodes — this is what gives the vulnerability rubric something real to correlate
     with);
   - a first-order lag (time constant 2–4 h, matching the report's stated diffusion lag) so the response
     is smoothed, not instantaneous — implement as an exponential moving average toward the target, not a
     step function.
2. Advance the node's **true core temperature**: baseline tracks a 24 h moving average of ambient, plus an
   optional **self-heating term** that scenarios can switch on — a slow exothermic ramp (see §5.3, hotspot
   scenario) representing fungal/germination respiration, deliberately decoupled from ambient so it reads
   as biological rather than solar.
3. **Invert the forward direction of Eq. in §6.2** to compute the *true* grain moisture `M_true` from
   `a_w` and temperature, tracking whether the node is currently in an adsorption (wetting) or desorption
   (drying) branch, and apply a small, distinct hysteresis offset per branch (0.5–1.5 %wb, per the report)
   so that later, when the gateway's isotherm inversion picks the wrong branch on purpose (see test cases
   in §5.5), the resulting bias is visible and explainable.
4. **Emit the observed reading** = true state + sensor noise + optional fault injection (§5.3):
   `ERH_observed = a_w * 100 + noise(σ≈1.5%)`, `T_observed = T_true + noise(σ≈0.3°C)`,
   `T_core_observed = T_core_true + noise(σ≈0.2°C)`.
5. Every reading carries its own timestamp, jittered ±0–90s off the nominal 15-minute grid, to force the
   gateway's time-alignment logic (§6.1) to actually do work rather than assume a perfect grid.

### 5.3 Scenario library (must implement at minimum these; each is a first-class, named, replayable config)

| Scenario | What it does | What the pipeline should show |
|---|---|---|
| `baseline_stable` | Stack sits comfortably below 14%, flat weather. | EPI stays in Normal band throughout. |
| `slow_monsoon_wetting` | Ambient RH ramps from ~70% to ~95% over 5–7 simulated days, sustained light rain. | `s_M` and `s_F` climb together; `dM/dt` visibly positive; EPI crosses into Watch then Priority with several hours of lead time — this is the scenario that proves objective O4's "median lead time" claim in software terms. |
| `core_hotspot` | One interior/core node's true core temperature ramps independently of ambient (biological self-heating), while ERH stays moderate. | `s_T` dominates the EPI rise on that one stack while `s_M` stays low — proves the sub-indices are actually decomposable, not just a moisture proxy in disguise. |
| `flash_rain_event` | A short, intense rainfall spike (high `p_rain`, high `R72`) with no time for `M_est` to have moved yet. | `s_F` spikes ahead of `s_M`/`s_R` — this is the "proactive not reactive" claim, made checkable. |
| `sensor_condensation_fault` | One node's local temperature crosses below the dew point derived from its own recent history; observed RH pins at ~100%. | Fault screening (§6.1) must catch and flag this node as suspect *without* letting it single-handedly drag the whole stack into a false Critical — verify via the stack's `n_ok`/neighbour-consistency logic. |
| `stuck_at_fault` | A node's readings freeze (variance ≈ 0 over a 6 h window) at a plausible-looking value. | Stuck-at detector (§6.1) flags it; stack falls back to the robust median of remaining healthy nodes. |
| `node_dropout` | A node stops transmitting entirely partway through the run. | Node Health screen shows last-seen time aging out; stack's `n_ok` decrements; if it drops below 2, the stack is flagged for manual inspection per the state-record contract. |
| `high_vulnerability_static` | A stack with poor tarpaulin/drainage/position score but merely average telemetry. | `s_V` alone should be enough to lift an otherwise middling stack noticeably up the ranking — proves the vulnerability term isn't decorative. |
| `override_breach` | Force `M_est ≥ 17.0` (or `MRA ≥ MRA_crit`) directly. | EPI safety override fires (`EPI ← max(EPI, 90)`) regardless of what the weighted sum alone would produce — must be independently unit-tested (§10). |
| `season_replay` | A long multi-week run mixing several of the above across many stacks concurrently, at accelerated clock speed, for the Season Report screen and for demoing the dispatch optimizer under real contention (more at-risk stacks than trucks). | Full pipeline, full dashboard, all screens populated with a coherent, explainable history. |

The scenario engine must support: choosing a scenario per stack independently (a 20-stack yard running a
mixed batch of the above simultaneously is the realistic demo state, not one scenario per whole yard),
starting/pausing/resetting the clock, and a speed multiplier (e.g. 1 simulated day per 10 real seconds) for
fast walkthroughs, with an option to run at "real" 15-minute cadence for a long-running background demo.

### 5.4 Weather feed

Two modes, switchable by config flag, same downstream schema either way:

- **`synthetic` (default, no external dependency):** a self-contained weather generator producing hourly
  `R72` (72 h cumulative forecast rainfall), `p_rain` (max probability of precipitation in-window), and
  `RH̄_f` (mean forecast RH), driven by a simple seasonal + scenario-scripted model so that
  `flash_rain_event` and `slow_monsoon_wetting` scenarios can deterministically script the forecast the way
  they script the ground truth — the forecast should sometimes *lead* the ground truth (proactive) and the
  demo should be able to show both a case where the forecast was right and, deliberately, one case where a
  forecast didn't fully materialize, so the dashboard's staleness/uncertainty handling (§8) has something
  real to display.
- **`live` (optional, feature-flagged):** a real Open-Meteo client for the yard's configured coordinates,
  used as a bonus/impressiveness layer for a live demo, wired through the exact same interface so the
  gateway code never knows which mode is active.

### 5.5 Testable contract for Module 1

Module 1 is not "just fake data" — it ships with its own test suite asserting: readings stay within
physically plausible bounds (0–100% RH, sane temperature ranges); the forward isotherm and the gateway's
inverse isotherm round-trip to within a stated tolerance in the no-noise, no-fault case; each scenario
produces the qualitative signature described in the table above (assert on the *shape* of the resulting
EPI/sub-index time series, not exact values); fault-injected nodes are distinguishable from healthy ones in
the raw stream before the gateway even processes them (i.e. the injection itself is correct).

---

## 6. MODULE 2 — Ingestion & State Reconstruction (the gateway, in software)

Implement precisely, with the exact formulas below. These are not approximations to be "improved" —
they are the contract the rest of the system depends on. Where a constant is given as "provisional" in the
source material, it must be a named, stored, editable configuration value (§9), never a literal in code.

### 6.1 Ingest & fault-screen (runs on every tick, per node)

1. **Time-align:** snap each reading to the nearest 15-minute grid slot; flag `stale` if the gap since the
   node's last accepted reading exceeds 2 cycles.
2. **Range check:** RH ∈ [0, 100], T ∈ a configurable plausible band (e.g. −5–60 °C) — reject outside.
3. **Stuck-at check:** variance of the node's last 6 h of readings below a configurable floor → flag
   `suspect`.
4. **Rate-of-change plausibility:** an RH step > ~15 points in one 15-minute interval inside a stack
   interior is implausible → flag `suspect` (this is the primary catch for the condensation scenario).
5. **Neighbour consistency:** compare each node's reading to the robust median (not mean) of its intra-stack
   cluster; persistent z-score above a configurable threshold → demote to `suspect`.
6. Only non-suspect, non-stale readings enter the state record. Track `n_ok` (surviving node count) and an
   overall `qflag` per stack per epoch. If `n_ok < 2`, mark the stack `needs_inspection` — this must surface
   visibly on the dashboard (§8.4), not just sit in the database.

### 6.2 Isotherm inversion (Modified Chung–Pfost)

```
RH = exp[ −A / (T + C) · exp(−B · M) ]
∴ M = −(1 / B) · ln[ −(T + C) · ln(RH) / A ]
```
where `M` = moisture content (decimal, dry basis), `T` = grain temperature (°C), `RH` = interstitial
relative humidity (decimal), `A`, `B`, `C` are material constants for rough rice, stored per-branch
(adsorption vs desorption — see §6.3) and editable in the settings store, not hardcoded.

Compute per node using its own `aw_max`-selected value (see below), then, per §6.4's state-record schema,
use the **worst-case** (`aw_max`) reading across surviving nodes in a stack for `M_est`, not the mean —
spoilage is local; averaging hides the nucleus. This must be implemented exactly this way; it is a
deliberate, documented design decision (log it in `DECISIONS.md`), not an oversight to "fix" toward a mean.

### 6.3 Branch selection (hysteresis handling)

Track the sign of the trailing `dM/dt` (§6.4) per stack. If rising → use adsorption-branch constants; if
falling → desorption-branch constants; store the currently active branch on the state record for
explainability (a reviewer should be able to see, per stack, "currently modelled as re-wetting" or "modelled
as drying").

### 6.4 Moisture derivative (rate of change)

Compute `dM/dt` over the trailing 24 h using a **Theil–Sen robust regression** (not ordinary least squares —
the whole point is resistance to the outliers that a transient condensation event produces). Use
`scipy.stats.theilslopes` or an equivalent robust-slope implementation; do not substitute a naive two-point
difference.

### 6.5 Mould Risk Accumulator (MRA)

```
MRA(t) = ∫[t−τ, t]  max(0, a_w(u) − 0.65) · Q10^((T(u)−25)/10)  du
```
with `Q10 = 2` (metabolic rate roughly doubles per 10 °C), `τ = 14 days`, `MRA_crit = 6.0 a_w·h`
(provisional — configurable). Implement as a numerically integrated running sum over the trailing window at
the 15-minute sampling cadence (trapezoidal or rectangle rule is fine — document which). The 0.65 threshold
below which storage fungi do not establish is likewise a configurable constant, not a literal.

### 6.6 Vulnerability rubric (`s_V` input — static, scored, not derived from telemetry)

Scored once at stack formation (or via the Settings/Stack-detail UI), on 5 factors — tarpaulin, dunnage/
plinth, drainage, position in row, residence time — each 0/1/2 points per the rubric table (reproduce the
exact categorical bands from the original design). Normalize as `(Σ points) / 10`. This must be editable
per-stack through the UI (an "audit update" control on the Stack Detail screen, §8.4), because it's the one
input that isn't telemetry-driven and a reviewer will specifically ask how it gets set and revised.

### 6.7 Fused state record (the Module 2 → Module 3 contract — implement as a strict schema)

One row per stack per 15-minute epoch:

| Field | Type/unit | Notes |
|---|---|---|
| `stack_id` | string | |
| `ts` | ISO-8601 UTC | |
| `aw_max` | decimal 0–1 | worst-case across surviving nodes |
| `M_est` | %wb | isotherm inversion at `aw_max` |
| `dM_dt_24h` | %wb·day⁻¹ | Theil–Sen slope |
| `T_core`, `T_amb_ma24` | °C | |
| `MRA` | a_w·h | |
| `R72`, `p_rain`, `RHf` | mm, 0–1, % | forecast scalars, common to the yard |
| `mass_t`, `age_d` | MT, days | from the stack card |
| `n_ok`, `qflag` | int, enum | surviving nodes / quality state |
| `active_branch` | enum | `adsorption` \| `desorption`, for explainability |

Persist this record — it is the audit trail the whole system's explainability rests on. Never recompute EPI
from raw telemetry directly inside Module 3; Module 3 must only ever read from this table.

### 6.8 Resilience requirement carried over from the original design

Module 2 must keep functioning with the last-cached forecast if the (synthetic-mode or live-mode) weather
feed is unavailable, with an explicit staleness indicator propagated all the way to the dashboard. Simulate
this: add a controllable "weather feed down" fault the demo can trigger, and verify the whole pipeline
degrades gracefully rather than crashing or silently freezing.

---

## 7. MODULE 3 — EPI Engine & Dispatch Optimizer

### 7.1 Sub-indices — exact formulas, weights as configurable defaults

`clamp01(x) = min(1, max(0, x))`

| Term | Formula | Default weight |
|---|---|---|
| `s_M` (state) | `clamp01((M_est − 14.0) / (17.0 − 14.0))` | 0.28 |
| `s_R` (rate) | `clamp01(dM_dt_24h / 0.5)` | 0.14 |
| `s_T` (thermal) | `clamp01((T_core − T_amb_ma24 − 2) / (8 − 2))` | 0.12 |
| `s_A` (accumulation) | `clamp01(MRA / 6.0)` | 0.18 |
| `s_F` (forecast) | `clamp01(0.7·p_rain·(R72/50) + 0.3·(RHf − 70)/25)` | 0.18 |
| `s_V` (vulnerability) | rubric score / 10 | 0.10 |

All six weights and all anchor constants (14.0, 17.0, 0.5, the ±2/8 thermal band, 6.0, the 50/70/25 forecast
constants) live in a single `weights_store` service, versioned, with every change timestamped and
attributable (§9) — never inlined.

### 7.2 EPI

```
EPI = 100 · (w_M·s_M + w_R·s_R + w_T·s_T + w_A·s_A + w_F·s_F + w_V·s_V)
subject to Σw_i = 1, w_i ≥ 0, s_i ∈ [0,1]

Override: if M_est ≥ 17.0 or MRA ≥ MRA_crit → EPI ← max(EPI, 90)
```

Bands (also configurable, ship these as defaults): `0–24 normal`, `25–49 watch`, `50–74 priority`,
`75–100 critical`.

Every computed EPI must be stored with the full sub-index vector and the weight vector active at
computation time — this is what makes "why is this stack ranked #3" answerable months later even after
weights have since been retuned.

### 7.3 Weight elicitation (AHP) as a real feature, not a footnote

Because the original design is explicit that "we chose them" is not an acceptable answer to a review panel,
build a small **AHP elicitation tool** into the Settings/Admin area: pairwise comparison inputs across the
six sub-indices, computed principal eigenvector, computed Consistency Ratio (flag if CR ≥ 0.10), and a
one-click "apply as new default weight set" that versions the previous set rather than overwriting it. This
does not need multi-user collaborative elicitation — a single-operator input form producing a valid
weight vector is sufficient — but it must be a real, working calculation, not a static form that saves
whatever numbers are typed in without validating consistency.

Also build a **sensitivity view**: given the current weight set, show how the top-6 ranking changes as each
weight is perturbed ±30%, one at a time. This can be a simple recompute-and-diff over the currently loaded
state records — no need for a separate simulation.

### 7.4 Dispatch optimization

Base problem (linear relaxation, solved by sorting):
```
maximise  Σ_i EPI_i · m_i · x_i
subject to  Σ_i m_i · x_i ≤ Q,  x_i ∈ {0,1}
```
Implement the **greedy-by-EPI-descending** baseline first (this is provably near-optimal for the
mass-weighted single-constraint case — implement and unit-test that claim directly: assert the greedy
result's total protected EPI·mass is within one stack's tonnage of a brute-force/ILP solution on small test
instances).

Then implement the **precedence-constrained** version: model yard access as a directed acyclic graph
(a stack blocking an aisle must be moved before the stack behind it), and add a **2-opt local search** over
that graph on top of the greedy baseline. Report, as a real computed metric surfaced in the UI (Season
Report screen), the improvement in protected tonne-EPI of the 2-opt result over the naive greedy baseline —
this comparison is a first-class deliverable, not incidental.

Precedence should be configurable per-yard (edit the yard plan / stack adjacency in Settings) — don't hardcode
a fixed graph; a demo yard needs at least one non-trivial precedence chain (a blocked stack scenario) to make
this module visibly do something beyond sorting.

### 7.5 Explainability requirement

Every ranked entry in a produced dispatch plan must carry a human-readable reason string generated from its
actual sub-index values, e.g. `"core 4.1°C above ambient; 38mm forecast in 48h"` — generate this
programmatically from whichever sub-indices are dominant for that stack (e.g., the top 1–2 sub-indices by
contribution to the weighted sum), never a static template that ignores the actual numbers.

---

## 8. MODULE 4 — Dashboard & Alerts (frontend)

### 8.1 Design brief — read this before writing any component

The subject is: a working agricultural procurement yard in Tamil Nadu, standing outdoors, in monsoon-season
light, operated by a supervisor on a mid-range Android phone with unreliable 3G, who has seconds — not
minutes — to decide which six of forty stacks to load onto today's trucks. This is **not** a SaaS analytics
dashboard, a fintech admin panel, or a generic "smart farm IoT" template. Every design decision should be
traceable back to that operator, that light condition, that device, and that task.

**Explicitly avoid** (these are the default tells of a generated interface, and none of them serve this
subject):
- A warm cream background with a high-contrast serif display and a terracotta/clay accent.
- A near-black background with one bright acid accent color.
- Uniform rounded "SaaS cards" with identical soft drop-shadows and gradient washes as decoration.
- Tracked-out ALL-CAPS eyebrow labels above every heading; meta text joined with middle-dots; a monospace
  face used purely for small data-label flavor; "→" appended to buttons/links as a tic.
- Fade-and-slide-up entrance animation on every section and a hover-lift on every card.
- Numbered 01/02/03 markers used decoratively where the content isn't actually a sequence.

**Ground the design in the real subject matter instead:**
- The primary color language should come from the domain itself, not a generic brand palette: bagged
  paddy, tarpaulin, wet monsoon concrete, weathered stack-card paper, hazard-tape yellows for the alert
  ladder. Pick 4–6 named hex values deliberately and write down *why* each one is there (e.g. "the Critical
  red is the same order of saturation as the hazard tape on a loading bay, not a generic UI-red").
- The **Yard Plan** screen is the hero, not a hero banner with a headline — it should be the first thing a
  supervisor sees, drawn as a schematic plan (not a map, not a 3D render) mirroring the yard's actual
  physical layout, oriented with the loading bay at the bottom, exactly as specified in the source design.
  Stacks are filled by EPI band color, sized by relative tonnage.
- Typography: choose one strong, functional sans (for dense operational data at arm's length in sunlight —
  legibility at a glance beats personality here) and, if a second face is used at all, use it sparingly and
  functionally (e.g. tabular figures for numeric read-outs), not decoratively.
- Motion: one deliberate moment is allowed — e.g., a stack visibly changing EPI band on the Yard Plan when
  a new tick arrives — and it should communicate the state change, not decorate the page. No hover
  animation on every element by default.
- Numbered process markers are legitimate on the **Loading Queue** screen because it genuinely is a
  sequence (1st truck, 2nd truck, ...) — use them there and nowhere else that isn't a real sequence.

Work in two passes, and record both in `docs/DECISIONS.md`: (1) a short written design plan — palette with
named hexes and rationale, type choices and roles, a layout concept with a one-paragraph description and an
ASCII wireframe per major screen, and a one-paragraph statement of what makes this specific build
identifiable as *this* yard's system and not a reskin of a generic dashboard; (2) a self-review against the
"avoid" list above before writing code, explicitly noting anything revised.

### 8.2 Screens (build all five; this is the same Module D from the source spec)

1. **Yard Plan** (default view) — schematic layout, stacks filled by EPI band, tap a stack for detail.
2. **Today's Loading Queue** — numbered list from the dispatch optimizer: stack ID, tonnage, EPI, estimated
   hours-to-breach, and the generated reason string (§7.5); running capacity bar against today's allocated
   tonnage; supervisor can override any entry, and overrides are logged with a reason code (persist these —
   they're explicitly future training/audit data per the source design, even though no ML model consumes
   them yet).
3. **Stack Detail** — 14-day trend of `M_est`, `a_w`, core-vs-ambient temperature, with 17% and 0.65
   threshold reference lines drawn in; per-node health; the vulnerability rubric with an edit control for
   audit updates (§6.6).
4. **Node Health** — battery-proxy, last-seen time, suspect flags, and a clear indicator of which stacks
   have fallen below 2 healthy nodes (`needs_inspection`). Maintenance/replacement actions are logged here
   (as data-entry, no physical dispatch needed in software mode).
5. **Season Report** — tonnes evacuated by EPI band, breaches "avoided" (define this precisely against
   simulated ground truth — a stack whose `M_est` was kept below 17% specifically because it was evacuated
   before a scripted wetting event completed), average lead time, node survival curve, and the greedy-vs-
   2-opt dispatch improvement metric from §7.4.

Add a sixth screen not in the original hardware-era spec, appropriate for a software-only build:

6. **Settings / Admin** — the weights store editor + AHP elicitation tool (§7.3), sensitivity view, isotherm
   constants (A/B/C per branch), MRA constants (`Q10`, `τ`, `MRA_crit`, the 0.65 threshold), alert-band
   boundaries, simulation controls (scenario picker per stack, clock speed, pause/resume/reset), and
   weather-feed mode toggle (`synthetic`/`live`).

### 8.3 Alert escalation ladder

Implement exactly, with hysteresis and dwell requirements (do not fire on a single noisy tick):

| Band | EPI | Trigger | Channel (software-simulated) | Expected action shown to operator |
|---|---|---|---|---|
| Normal | 0–24 | — | Dashboard only | Routine |
| Watch | 25–49 | sustained ≥ 3 h | Dashboard badge; daily digest | Include in next dry-weather movement |
| Priority | 50–74 | sustained ≥ 2 h | In-app push + simulated SMS (Tamil) | Load within 48 h; verify tarpaulin now |
| Critical | 75–100 | sustained ≥ 30 min, or override fired | Simulated SMS to supervisor + district office; audible in-app alarm | Load within 24 h; inspect immediately |

De-escalation uses a 10-point hysteresis band and a 6-hour dwell before downgrading. "Simulated SMS" means:
render it as an actual message object in a visible **Alerts / Messages log** in the UI (with the exact
Tamil-language copy that would be sent) rather than actually integrating a telecom API — this is a software
project, and faking the transport while keeping the content and logic real is the correct scope line. Every
alert carries its reason string and the specific node IDs that drove it.

### 8.4 Empty/failure states

Per the frontend-design principle of treating failure and emptiness as moments for direction: a yard with no
stacks yet, a stack with `n_ok < 2`, a weather feed that's stale, and an offline dashboard should each have
a deliberate, specific, plain-language treatment explaining what's true and what to do — never a generic
spinner-forever or a bare "no data" string.

### 8.5 Copy

Write real copy for every label, button, and message — no lorem ipsum, no placeholder "Lorem" screens shipped
as final. Buttons name the action they perform ("Confirm loading order," not "Submit"); the vocabulary
introduced on one screen (e.g. "suspect," "needs inspection," "override") must be used identically
everywhere else it appears.

### 8.6 Responsiveness

Primary target is a mid-range Android phone in portrait, in direct sunlight (design for high-contrast
legibility, not just "looks fine on a laptop"). Must also work acceptably on a desktop browser for the
district-officer read-only cross-yard view mentioned in §8.7's role list.

### 8.7 Localization

Ship English and Tamil (`en.json` / `ta.json`) from the start, including all alert copy and the reason
strings (the reason-string generator in §7.5 must be localizable, not hardcoded English text interpolated
into a Tamil sentence).

### 8.8 Offline tolerance (PWA)

Build as an installable PWA with a service worker caching the last synchronized Yard Plan and Loading Queue,
so both remain readable with no connectivity — simulate a "gateway offline" condition (reuse the weather-feed-
down fault from §6.8, or add a dedicated one) and verify the frontend degrades to cached data with a visible,
honest "last synced at …" indicator rather than a blank screen or stale data presented as live.

### 8.9 Roles

Implement basic role separation even without full auth infra: **supervisor** (acts — sees queue, can
override), **quality inspector** (audits — can edit vulnerability rubric and node-health notes),
**district officer** (read-only cross-yard view). A simple role switcher for demo purposes is acceptable;
a production auth system is out of scope unless explicitly requested later.

---

## 9. Configuration & explainability layer (cross-cutting requirement)

Every constant that appears in §§6–7 (isotherm A/B/C per branch, the 14.0/17.0 anchors, the 0.5 rate anchor,
the ±2/8 thermal band, `MRA_crit`, `Q10`, `τ`, the 0.65 fungal threshold, the forecast formula's 50/70/25
constants, all six EPI weights, the alert-band boundaries, the hysteresis/dwell durations) must live in one
place (`weights_store` / a `config` table), be readable via an API endpoint, editable via the Settings
screen, and **versioned** — every past computation stays attributable to the config version active when it
ran. This is what turns "we picked these numbers" into "here is exactly what we believed and when, and here
is how to audit it," which is the actual point of the exercise.

---

## 10. Testing & validation requirements

- **Unit tests** for the isotherm inversion (round-trip against the forward model in Module 1, both
  branches), the Theil–Sen slope computation, the MRA integral (verify the worked example: 24h at
  `a_w=0.75`, 25°C → 2.4 a_w·h; same at 35°C → 4.8, per the source spec — this exact number must reproduce),
  each sub-index formula at boundary values (0, 1, and the override thresholds), the EPI override rule
  fired and not-fired, and the greedy-vs-optimal dispatch bound.
- **Scenario-level integration tests**: for each named scenario in §5.3, assert the qualitative signature
  described in that table actually emerges from running the full pipeline end-to-end on synthetic input —
  this is the test suite that proves Modules 1–3 are honestly wired together, not just individually correct.
- **Fault-injection tests**: verify a `sensor_condensation_fault` node is excluded from `M_est` computation
  and does not solely trigger a stack-level Critical alert.
- **Precision@k style evaluation**: using a `season_replay` run with scripted "true" spoilage events (the
  simulator knows ground truth because it generated it), compute Precision@6 for the EPI ranking against
  that ground truth and surface it on the Season Report screen — this operationalizes objective O4's
  precision target in a fully synthetic, fully reproducible way, with no field data required.
- **Frontend**: at minimum, component tests for the Yard Plan band-coloring logic, the Loading Queue capacity
  bar, and the alert-ladder hysteresis/dwell behaviour; a manual design self-review checklist (from §8.1)
  logged in `DECISIONS.md` before calling any screen done.

---

## 11. Explicit exclusions (say no to these if asked mid-build)

- No firmware, no embedded C, no radio protocol stack, no PCB/BOM, no battery/energy modelling beyond a
  cosmetic decaying proxy value for the Node Health screen.
- No real SMS/telecom integration — simulate the message content and log, per §8.3.
- No requirement for a real weather API key to run the core demo — `synthetic` mode must be fully
  self-sufficient (§5.4); `live` mode is additive.
- No machine-learned model anywhere in the critical path — the EPI is, deliberately, a physics-informed
  weighted index per the source design's own stated rationale (interpretable, auditable, operable with zero
  training data); don't "improve" it into a black box.

---

## 12. Deliverables checklist

- [ ] Module 1 simulator: node/stack/yard models, forward isotherm, all named scenarios, weather feed
      (synthetic + optional live), clock control, own test suite.
- [ ] Module 2 gateway: time-alignment, all four fault-screening tests, isotherm inversion with branch
      selection, Theil–Sen `dM/dt`, MRA integral, fused state-record persistence, weather-feed resilience.
- [ ] Module 3 engine: all six sub-indices, EPI + override, versioned/editable weights store, AHP
      elicitation tool with Consistency Ratio, sensitivity view, greedy dispatch + precedence-aware 2-opt,
      reason-string generation.
- [ ] Module 4 frontend: all six screens (§8.2), alert ladder with hysteresis/dwell, empty/failure states,
      bilingual copy, responsive/offline-tolerant PWA, role switcher — built to the design brief in §8.1,
      with the two-pass design plan and self-review logged in `docs/DECISIONS.md`.
- [ ] Live WebSocket/SSE update path from backend clock tick to frontend, end to end.
- [ ] Full test suite per §10, passing.
- [ ] `docs/DECISIONS.md` and `docs/SCENARIOS.md` populated and current.
- [ ] README covering: how to run the simulator, how to switch scenarios, how to run the full stack locally,
      how to reset state.
