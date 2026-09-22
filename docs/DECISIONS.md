# Architectural & Design Decisions Log

## 1. Frontend Design Plan (Two-Pass Design Process)

### Pass 1: Written Design Plan & Grounding

#### Real-World Context & Operational Subject Matter
The system is built for a working agricultural procurement yard (Direct Purchase Centre / Open Storage Yard) in Thanjavur / Tiruvarur district, Tamil Nadu. The operator is a yard supervisor standing outdoors on packed earth and cracked monsoon concrete, holding a mid-range Android smartphone with greasy fingers in direct, glaring tropical sunlight or drizzle. 

The supervisor has seconds—not minutes—to make operational decisions:
- Which stacks must be covered or checked immediately?
- Which stacks take priority for today's arriving 10-tonne and 20-tonne trucks?
- Is an elevated reading caused by a real biological hotspot (fungal respiration) or a faulty sensor?

Every visual element must be immediately legible at arm's length in bright ambient glare. There is zero tolerance for delicate pastel badges, low-contrast grey-on-grey typography, or decorative distractions.

#### Domain-Grounded Color Palette (2026 rebuild — tarpaulin-green outdoor console)

The previous cream / Inter / red-card treatment read as a generic generated dashboard and failed sunlight contrast. Rebuild identity: **laminated HDPE-tarpaulin clipboard on wet monsoon concrete**. Green is the chrome and the healthy band, not a decorative accent on cream cards.

| Token Name | Hex Value | Physical Yard Reference | Operational Purpose |
|---|---|---|---|
| `--tarp-shade` | `#0C2F24` | HDPE tarpaulin in shade | Header, weighbridge slab, numbered queue marks |
| `--tarp-field` | `#176B45` | Sunlit procurement tarpaulin | Primary actions, live sync, capacity fill |
| `--paddy-canopy` | `#1F7A4C` | Standing paddy canopy | Normal band (EPI 0–24) stack fill |
| `--wet-slab` | `#C5D0C8` | Wet monsoon concrete | Page ground (cool, not cream `#F4F1EA`) |
| `--clipboard` | `#F1F6F2` | Laminated field clipboard | Instrument rail, panels |
| `--ink` | `#0D1F18` | Carbon stencil on tarp | Body text (>12:1 on clipboard) |
| `--road-paint` | `#C9891A` | Weathered yellow road marking | Watch band |
| `--priority-ochre` | `#C45C12` | Rusted bay stencils | Priority band |
| `--hazard-tape` | `#B42318` | Loading-bay hazard tape | Critical band, inspection banners |

Catalog check: 21st.dev “Green Notes” (cream + Inter + serif) and “Matrix Green” (near-black + acid) were rejected as §8.1 anti-patterns. “SeaGreen Minimal” contributed only the tight 2px radius and cool green family; tokens were rewritten against tarpaulin / concrete, not shadcn variables.

#### Typography & Visual Roles
- **Primary Typeface:** `IBM Plex Sans` — industrial, designed for dense operational data, not Inter/SaaS defaults.
- **Tamil:** `Noto Sans Tamil` stacked in the same family list so bilingual labels never fall back to a serif.
- **Tabular Figures:** `font-variant-numeric: tabular-nums` on every telemetry readout so live ticks do not jitter layout.
- **No second display face.** Personality comes from the yard schematic (hatched drainage ditch, dashed 6 m aisle, weighbridge slab), not from type theatrics.

#### Screen Wireframes (ASCII)

##### 1. Yard Plan (Hero View)
```
┌────────────────────────────────────────────────────────────┐
│ [YARD PLAN]   Sim: 14:45 (Day 4)   Speed: 10x  [PAUSE]  Ta │
├────────────────────────────────────────────────────────────┤
│ [WEATHER: 🌧️ Rain 4.2mm/h | R72: 48mm | p_rain: 85%]        │
├────────────────────────────────────────────────────────────┤
│                    NORTH BOUNDARY / DRAINAGE               │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐            │
│  │ STK-01 │  │ STK-02 │  │ STK-03 │  │ STK-04 │  (Row A)   │
│  │ 82 CRIT│  │ 18 NORM│  │ 42 WTCH│  │ 68 PRI │            │
│  └────────┘  └────────┘  └────────┘  └────────┘            │
│       ▲ BLOCKS AISLE 1                                     │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐            │
│  │ STK-05 │  │ STK-06 │  │ STK-07 │  │ STK-08 │  (Row B)   │
│  │ 55 PRI │  │ 12 NORM│  │ 31 WTCH│  │ 15 NORM│            │
│  └────────┘  └────────┘  └────────┘  └────────┘            │
│                 MAIN APRON ROADWAY                         │
├────────────────────────────────────────────────────────────┤
│ [== LOADING BAY / WEIGHBRIDGE ==]  Truck Capacity: 120 MT  │
└────────────────────────────────────────────────────────────┘
```

##### 2. Loading Queue
```
┌────────────────────────────────────────────────────────────┐
│ TODAY'S LOADING SEQUENCE (Truck Allotment: 120 MT)         │
│ Allocated: [████████████████░░░░] 96 / 120 MT              │
├────────────────────────────────────────────────────────────┤
│ #1 [TRUCK 1] STK-01 (48 MT) - EPI: 91 [CRITICAL OVERRIDE]  │
│    Reason: M_est 17.4% >= 17.0% safety threshold; 48mm rain │
│    Precedence: Front of Aisle 1 (Immediate clearance)      │
│    [OVERRIDE]                                              │
├────────────────────────────────────────────────────────────┤
│ #2 [TRUCK 2] STK-04 (48 MT) - EPI: 68 [PRIORITY]           │
│    Reason: Core 4.2°C > ambient; biological self-heating   │
│    [OVERRIDE]                                              │
└────────────────────────────────────────────────────────────┘
```

##### 3. Stack Detail & Vulnerability Rubric
```
┌────────────────────────────────────────────────────────────┐
│ STK-01 DETAIL (Age: 42d | 48 MT | 4/4 Nodes Active)        │
│ EPI: 91 [CRITICAL] (s_M: 1.0, s_R: 0.8, s_T: 0.3, s_F:0.9)│
├────────────────────────────────────────────────────────────┤
│ 14-DAY MOISTURE & aw TREND (Custom SVG)                    │
│ 18% ──────────────────── [17% SAFETY THRESHOLD] ────────── │
│ 16%           . - - - * (M_est = 17.4%)                    │
│ 14% ────. - ' ──────────────────────────────────────────── │
├────────────────────────────────────────────────────────────┤
│ VULNERABILITY AUDIT (Current Score: 0.70)                  │
│ Tarpaulin: [0 Intact | 1 Minor wear | (2 Torn/Patched) ]   │
│ Dunnage:   [0 Concrete | (1 Wood Pallets) | 2 Dirt Floor]  │
│ Drainage:  [0 High ground | 1 Mild slope | (2 Depressed) ] │
│ Position:  [0 Interior | 1 End row | (2 Outer windward) ]  │
│ Age:       [(0 <30d) | 1 30-90d | 2 >90d ]                 │
│ [SAVE AUDIT REVISION]                                      │
└────────────────────────────────────────────────────────────┘
```

**What makes this *this* yard's system:** the first paint is a physical schematic — hatched north drainage, two bag-pile rows, a dashed 6 m forklift aisle, weighbridge slab at the bottom — filled with tarpaulin-green / road-paint / hazard-tape, not KPI widgets. The header is a tractor-style LCD cluster (sim clock, RH, live/offline), not a SaaS product bar. Tamil and English swap the same labels; nothing is hardcoded stack theatre.

---

### Pass 2: Self-Review Against §8.1 Prohibitions

| Prohibited Anti-Pattern | Check Status | How It Was Addressed in This Build |
|---|---|---|
| *Warm cream background + serif display + terracotta accent* | **Compliant** | Cool wet-slab `#C5D0C8` + tarpaulin green chrome. IBM Plex Sans only. No serif, no cream `#F4F1EA`. |
| *Near-black background with bright acid accent* | **Compliant** | Daylight slab background; header is shaded tarpaulin `#0C2F24`, not OLED black. Accents are HDPE green / road paint, not acid lime. |
| *Uniform rounded "SaaS cards" with soft drop-shadows* | **Compliant** | 2px radius, 2px ink borders, zero drop shadows. KPI is one instrument rail, not four identical cards. |
| *Tracked-out ALL-CAPS eyebrow labels above every heading* | **Compliant** | Standard sentence case / title case headers with clear typographic hierarchy. |
| *Meta text joined with middle-dots* | **Compliant** | Functional bracketed or tabular delimiters (`[48 MT]`, `Row A · Aisle 1` used only where semantically appropriate). |
| *Monospace face used decoratively for small labels* | **Compliant** | Monospace / tabular numbers reserved strictly for numeric telemetry and data fields. |
| *Fade-and-slide entrance on every section / hover lift* | **Compliant** | Strictly functional state-transition highlights (e.g. pulse when a stack changes EPI band on a tick). Zero decorative entrance lag. |
| *Numbered 01/02 markers used decoratively* | **Compliant** | Numbers 1, 2, 3... are strictly confined to **Today's Loading Queue** where they denote actual truck loading sequences. |

---

## 2. Technical & Mathematical Architecture Decisions

### 1. Modified Chung–Pfost Rough Rice Sorption Isotherm
- Equation:
  $$M = -\frac{1}{B} \cdot \ln\left[ -\frac{(T + C) \cdot \ln(RH)}{A} \right]$$
  $$RH = \exp\left[ -\frac{A}{T + C} \cdot \exp(-B \cdot M) \right]$$
- Standard rough rice parameters (ASABE D245.7):
  - **Adsorption branch (re-wetting):** $A = 502.8$, $B = 16.5$, $C = 41.5$.
  - **Desorption branch (drying):** $A = 591.4$, $B = 16.8$, $C = 35.7$.
- **Hysteresis Branch Selection:** Track the sign of trailing 24h $dM/dt$. If $dM/dt \ge 0 \implies$ Adsorption branch; if $dM/dt < 0 \implies$ Desorption branch.

### 2. Worst-Case ($aw_{max}$) vs Mean Pooling
- **Decision:** Stack grain moisture $M_{est}$ is calculated from the node reporting the highest water activity ($aw_{max}$), NOT the spatial mean across nodes.
- **Rationale:** Grain spoilage and mycotoxin formation are local nucleating phenomena. Averaging wet perimeter nodes with dry core nodes hides mould incubation hotspots until whole-stack spoilage has occurred.

### 3. Theil–Sen Robust Regression for Rate of Change ($dM/dt$)
- **Decision:** Calculate $dM/dt$ over the trailing 24-hour window using `scipy.stats.theilslopes`.
- **Rationale:** Condensation events or sensor noise create transient single-epoch outliers. Ordinary Least Squares (OLS) has an unbounded influence function and would produce wild derivative spikes. Theil–Sen has a breakdown point of ~29.3%, ensuring stable, physically honest rates.

### 4. Mould Risk Accumulator (MRA)
- Trailing window $\tau = 14\text{ days}$ (336 hours), $Q_{10} = 2.0$, fungal baseline threshold $a_w = 0.65$.
- Exact reference verification:
  - 24h at $a_w = 0.75, 25^\circ\text{C} \implies (0.75 - 0.65) \cdot 2^{(25-25)/10} \cdot 24\text{h} = 0.10 \cdot 1 \cdot 24 = 2.4\,a_w\cdot\text{h}$.
  - 24h at $a_w = 0.75, 35^\circ\text{C} \implies 0.10 \cdot 2^{(35-25)/10} \cdot 24 = 0.10 \cdot 2 \cdot 24 = 4.8\,a_w\cdot\text{h}$.

### 5. Analytic Hierarchy Process (AHP) Weight Elicitation
- $6 \times 6$ reciprocal pairwise comparison matrix.
- Computed via principal eigenvector (Perron-Frobenius theorem) using NumPy.
- Consistency Ratio $CR = CI / RI$ with $RI(6) = 1.24$. $CR < 0.10$ required for validation before versioned commit.

### 6. Precedence-Constrained Dispatch Optimizer
- 0-1 Knapsack problem with yard aisle access DAG.
- Stacks in outer positions block access to inner stacks.
- Greedy baseline provides initial packing. 2-opt local search swaps items and resolves precedence violations to maximize protected tonne-EPI.
