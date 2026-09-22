# Synthetic Telemetry Scenarios Catalogue

This document details the 10 first-class synthetic scenarios implemented in the platform. Each scenario runs either across an entire yard or on a per-stack assignment basis, generating physically honest telemetry with clear qualitative signatures.

---

## 1. `baseline_stable`
- **Physical Context:** Stack is stored in dry, sheltered conditions. Ambient RH fluctuates between 55% and 65%, ambient temperature 24°C–32°C.
- **Node Dynamics:**
  - Water activity $a_w \approx 0.58\text{--}0.62$.
  - Core temperature tracks 24h ambient moving average without self-heating.
  - Rate of change $dM/dt \approx 0.0\,\%wb/\text{day}$.
- **Expected Pipeline Behavior:**
  - Moisture $M_{est} \approx 12.5\%\text{--}13.2\%$ (well below 14.0% threshold).
  - Sub-indices $s_M = 0, s_R = 0, s_T = 0, s_A = 0, s_F \approx 0.1, s_V \le 0.3$.
  - **EPI:** 5–18 (Normal band throughout).

---

## 2. `slow_monsoon_wetting`
- **Physical Context:** Persistent monsoon depression. Ambient RH ramps from 70% to 95% over 5–7 simulated days with sustained drizzle/light rain.
- **Node Dynamics:**
  - Perimeter and ground-contact nodes absorb moisture first ($a_w$ rises toward 0.82), followed by interior nodes with a 3h exponential lag.
  - $dM/dt$ climbs to $+0.3\text{--}0.6\,\%wb/\text{day}$.
  - Accumulator $MRA$ begins integrating once $a_w > 0.65$.
- **Expected Pipeline Behavior:**
  - $s_M$ and $s_F$ climb steadily together.
  - EPI progresses deterministically: **Normal $\to$ Watch $\to$ Priority** with $> 48$ hours lead time before exceeding 17.0%. Demonstrates proactive dispatch lead time.

---

## 3. `core_hotspot`
- **Physical Context:** Internal fungal colony or micro-germination in deep core grain, while exterior tarpaulin and perimeter appear dry.
- **Node Dynamics:**
  - Deep-core node reports autonomous biological self-heating: temperature ramps +0.2°C to +0.5°C per simulated day above ambient, reaching $\Delta T = T_{core} - T_{amb\_ma24} > 6^\circ\text{C}$.
  - Moisture remains moderate ($M_{est} \approx 14.2\%$).
- **Expected Pipeline Behavior:**
  - Thermal sub-index $s_T$ spikes sharply to $0.8\text{--}1.0$.
  - $s_M$ and $s_F$ remain low ($< 0.2$).
  - Proves sub-index decomposability: the supervisor sees a Priority/Critical alert driven strictly by internal thermal respiration.

---

## 4. `flash_rain_event`
- **Physical Context:** Sudden severe convective thunderstorm: $R72 = 65\text{ mm}$, $p_{rain} = 0.95$.
- **Node Dynamics:**
  - Heavy rain starts immediately, but diffusion lag through tarpaulin and burlap prevents internal grain moisture $M_{est}$ from changing in the first 2 hours.
- **Expected Pipeline Behavior:**
  - Forecast sub-index $s_F$ immediately spikes to $0.85\text{--}1.0$.
  - $s_M$ and $s_R$ remain at zero initially.
  - EPI jumps into Watch or Priority prior to moisture ingress, proving the proactive nature of the forecast integration.

---

## 5. `sensor_condensation_fault`
- **Physical Context:** Rapid evening radiative cooling causes cold air on an outer lance node to cross dew point; interstitial liquid condensation coats the capacitive RH sensor, causing it to read 99.8% RH.
- **Node Dynamics:**
  - Targeted node reports sudden step change: RH jumps from 65% to 100% in a single 15-minute interval ($|\Delta RH| = 35\% > 15\%$).
  - Surrounding nodes in the same stack cluster remain at 64%–68%.
- **Expected Pipeline Behavior:**
  - **Fault screening** flags the node as `suspect` due to rate-of-change plausibility and intra-stack cluster median z-score check.
  - The faulty 100% reading is excluded from the stack's $aw_{max}$ calculation.
  - The stack does **not** trigger a false Critical alert. $n_{ok}$ drops by 1.

---

## 6. `stuck_at_fault`
- **Physical Context:** Analog-to-digital converter (ADC) freeze or firmware state lock on a single lance node.
- **Node Dynamics:**
  - Node emits identical values: $RH = 67.4\%$, $T = 28.2^\circ\text{C}$ with zero variance over a 6-hour rolling window ($var < 10^{-4}$).
- **Expected Pipeline Behavior:**
  - Stuck-at detector in Module 2 flags the node as `suspect`.
  - Node is excluded from state reconstruction. Stack relies on remaining healthy nodes.

---

## 7. `node_dropout`
- **Physical Context:** Battery failure, physical cable cut by rodents, or radio transceiver fault.
- **Node Dynamics:**
  - Node ceases all transmissions midway through the simulation run.
- **Expected Pipeline Behavior:**
  - Gateway detects missing timestamps; flags node as `stale` after 2 missing cycles, then `lost`.
  - Surviving node count $n_{ok}$ decrements.
  - When $n_{ok} < 2$, the stack automatically trips the `needs_inspection` flag, surfacing an urgent physical check alert on the dashboard.

---

## 8. `high_vulnerability_static`
- **Physical Context:** Stack built on low-lying ground with torn tarpaulins and weathered wooden pallets, but under mild dry weather conditions.
- **Node Dynamics:**
  - Telemetry is normal ($a_w \approx 0.60$, $M_{est} \approx 13.0\%$).
- **Expected Pipeline Behavior:**
  - Vulnerability rubric score $s_V = 0.90\text{--}1.0$ (maximum static risk).
  - Elevates stack EPI into Watch band even with pristine telemetry, ensuring compromised physical infrastructure is prioritized before weather arrives.

---

## 9. `override_breach`
- **Physical Context:** Catastrophic flood or heavy tarpaulin collapse driving grain moisture $M_{est} \ge 17.0\%$ or $MRA \ge 6.0\,a_w\cdot\text{h}$.
- **Node Dynamics:**
  - Node $a_w$ forced to $0.88$, generating $M_{est} = 17.6\%$.
- **Expected Pipeline Behavior:**
  - Hard safety override fires: $\text{EPI} \leftarrow \max(\text{EPI}, 90)$.
  - Bypasses weighted sum to pin at Critical band ($90\text{--}100$).
  - Immediately triggers Critical SMS alert copy in Tamil & English.

---

## 10. `season_replay`
- **Physical Context:** Multi-week simulated procurement season across 12–20 stacks simultaneously.
- **Dynamic Progression:**
  - Mixes all above scenarios across different stacks (some stable, some wetting, some hotspots, some faults).
  - Contention: More stacks in Priority/Critical than available daily truck capacity (e.g. 120 MT available, 240 MT at risk).
- **Expected Pipeline Behavior:**
  - Demonstrates full dispatch optimizer: DAG precedence resolution, 2-opt sequence optimization, lead time calculation, and Precision@6 evaluation against true simulated spoilage ground truth.
