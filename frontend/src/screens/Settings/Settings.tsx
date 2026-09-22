import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../lib/api-client";
import { useLive } from "../../state/LiveStore";
import type { SettingsPayload, SubIndexWeights } from "../../types";

const SCENARIOS = [
  "baseline_stable",
  "slow_monsoon_wetting",
  "core_hotspot",
  "flash_rain_event",
  "sensor_condensation_fault",
  "stuck_at_fault",
  "node_dropout",
  "high_vulnerability_static",
  "override_breach",
  "season_replay",
];

const SPEEDS = [1, 10, 60, 900];
const ORDER = ["s_M", "s_R", "s_T", "s_A", "s_F", "s_V"] as const;

function identityMatrix(): number[][] {
  return Array.from({ length: 6 }, (_, i) => Array.from({ length: 6 }, (__, j) => (i === j ? 1 : 1)));
}

export function Settings() {
  const { t } = useTranslation();
  const { yard, controlSim, role } = useLive();
  const [settings, setSettings] = useState<SettingsPayload | null>(null);
  const [stackId, setStackId] = useState("STK-01");
  const [scenario, setScenario] = useState(SCENARIOS[0]);
  const [matrix, setMatrix] = useState<number[][]>(identityMatrix());
  const [ahp, setAhp] = useState<{ cr: number; weights: number[]; ok: boolean } | null>(null);
  const [sens, setSens] = useState<{
    baseline_top6?: string[];
    perturbation_percent?: number;
    analyses?: Record<string, { sub_index: string; direction: string; ranking_shifted: boolean; top6_ranking: string[]; perturbed_weight: number }>;
  } | null>(null);
  const [author, setAuthor] = useState("Supervisor");
  const [rationale, setRationale] = useState("AHP re-elicitation from yard floor");
  const canEdit = role === "supervisor";

  useEffect(() => {
    api.settings().then(setSettings).catch(() => setSettings(null));
    api.sensitivity().then(setSens).catch(() => setSens(null));
  }, []);

  const setCell = (i: number, j: number, raw: number) => {
    const v = Math.max(1 / 9, Math.min(9, raw || 1));
    setMatrix((m) => {
      const next = m.map((row) => [...row]);
      next[i][j] = v;
      next[j][i] = 1 / v;
      next[i][i] = 1;
      next[j][j] = 1;
      return next;
    });
  };

  const solve = async () => {
    const res = await api.solveAhp(matrix);
    setAhp({ cr: res.consistency_ratio, weights: res.normalized_weights, ok: res.is_consistent });
  };

  const commit = async () => {
    if (!ahp?.ok || !canEdit) return;
    const weights: SubIndexWeights = {
      w_M: ahp.weights[0],
      w_R: ahp.weights[1],
      w_T: ahp.weights[2],
      w_A: ahp.weights[3],
      w_F: ahp.weights[4],
      w_V: ahp.weights[5],
    };
    await api.applyWeights(weights, author, rationale);
    setSettings(await api.settings());
  };

  return (
    <>
      <section className="panel">
        <h2>{t("settings.clock")}</h2>
        <div className="form-row">
          <button className="btn" type="button" disabled={!canEdit} onClick={() => void controlSim({ action: "play" })}>
            {t("settings.play")}
          </button>
          <button className="btn ghost" type="button" disabled={!canEdit} onClick={() => void controlSim({ action: "pause" })}>
            {t("settings.pause")}
          </button>
          <button className="btn ghost" type="button" disabled={!canEdit} onClick={() => void controlSim({ action: "step" })}>
            {t("settings.step")}
          </button>
          <button className="btn ghost" type="button" disabled={!canEdit} onClick={() => void controlSim({ action: "reset" })}>
            {t("settings.reset")}
          </button>
        </div>
        <div className="k">{t("settings.speed")}</div>
        <div className="seg">
          {SPEEDS.map((s) => (
            <button
              key={s}
              type="button"
              className={yard?.speed_multiplier === s ? "on" : ""}
              disabled={!canEdit}
              onClick={() => void controlSim({ action: "set_speed", speed_multiplier: s })}
            >
              {s}×
            </button>
          ))}
        </div>
        <div className="k" style={{ marginTop: 10 }}>
          {t("settings.weather")}: {yard?.weather_mode}
        </div>
        <div className="form-row">
          <button className="btn ghost" type="button" disabled={!canEdit} onClick={() => void controlSim({ action: "toggle_weather_mode", weather_mode: yard?.weather_mode === "live" ? "synthetic" : "live" })}>
            {yard?.weather_mode === "live" ? t("settings.synthetic") : t("settings.liveWx")}
          </button>
          <button className="btn ghost" type="button" disabled={!canEdit} onClick={() => void controlSim({ action: "toggle_weather_fault" })}>
            {t("settings.wxFault")}
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>{t("settings.scenario")}</h2>
        <div className="form-row">
          <select value={stackId} onChange={(e) => setStackId(e.target.value)}>
            {(yard?.stacks ?? []).map((s) => (
              <option key={s.stack_id} value={s.stack_id}>
                {s.stack_id}
              </option>
            ))}
          </select>
          <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
            {SCENARIOS.map((s) => (
              <option key={s} value={s}>
                {t(`settings.scenarios.${s}`)}
              </option>
            ))}
          </select>
          <button
            className="btn"
            type="button"
            disabled={!canEdit}
            onClick={() => void controlSim({ action: "assign_scenario", stack_id: stackId, scenario_name: scenario })}
          >
            {t("settings.applyScenario")}
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>{t("settings.weights", { v: settings?.version_id ?? 1 })}</h2>
        {settings && (
          <ul>
            {ORDER.map((k) => {
              const wk = `w_${k.slice(2)}` as keyof SubIndexWeights;
              return (
                <li key={k}>
                  {t(`sub.${k}`)}: {settings.weights[wk].toFixed(3)}
                </li>
              );
            })}
          </ul>
        )}
        <h3>{t("settings.ahp")}</h3>
        <table className="ahp">
          <thead>
            <tr>
              <th />
              {ORDER.map((k) => (
                <th key={k}>{t(`sub.${k}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ORDER.map((row, i) => (
              <tr key={row}>
                <th>{t(`sub.${row}`)}</th>
                {ORDER.map((col, j) => (
                  <td key={col}>
                    {i === j ? (
                      "1"
                    ) : i < j ? (
                      <input
                        type="number"
                        min={0.11}
                        max={9}
                        step={0.1}
                        value={Number(matrix[i][j].toFixed(2))}
                        disabled={!canEdit}
                        onChange={(e) => setCell(i, j, Number(e.target.value))}
                      />
                    ) : (
                      matrix[i][j].toFixed(2)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="form-row">
          <input value={author} disabled={!canEdit} onChange={(e) => setAuthor(e.target.value)} aria-label={t("settings.author")} />
          <input value={rationale} disabled={!canEdit} onChange={(e) => setRationale(e.target.value)} aria-label={t("settings.rationale")} />
          <button className="btn ghost" type="button" onClick={() => void solve()}>
            {t("settings.solve")}
          </button>
          <button className="btn" type="button" disabled={!canEdit || !ahp?.ok} onClick={() => void commit()}>
            {t("settings.commit")}
          </button>
        </div>
        {ahp && (
          <p>
            {t("settings.cr")}: {ahp.cr.toFixed(3)} — {ahp.ok ? t("settings.consistent") : t("settings.inconsistent")}
          </p>
        )}
      </section>

      <section className="panel">
        <h2>{t("settings.sensitivity")}</h2>
        {sens?.baseline_top6 ? (
          <>
            <p className="k">
              {t("settings.baseline")}: {sens.baseline_top6.join(" · ")}
            </p>
            <table className="kv">
              <thead>
                <tr>
                  <th />
                  <th>{t("settings.plus")}</th>
                  <th>{t("settings.minus")}</th>
                </tr>
              </thead>
              <tbody>
                {ORDER.map((k) => {
                  const plus = sens.analyses?.[`${k}_plus_30`];
                  const minus = sens.analyses?.[`${k}_minus_30`];
                  return (
                    <tr key={k}>
                      <th>{t(`sub.${k}`)}</th>
                      <td>{plus?.ranking_shifted ? t("settings.shifted") : t("settings.held")}</td>
                      <td>{minus?.ranking_shifted ? t("settings.shifted") : t("settings.held")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </>
        ) : (
          <p>—</p>
        )}
      </section>

      {settings && (
        <section className="panel">
          <h2>{t("settings.constants")}</h2>
          <table className="kv">
            <tbody>
              {Object.entries({ ...settings.anchors, ...settings.alert_ladder }).map(([k, v]) => (
                <tr key={k}>
                  <th>{k}</th>
                  <td className="num">{String(v)}</td>
                </tr>
              ))}
              <tr>
                <th>adsorption A/B/C</th>
                <td className="num">
                  {settings.isotherm_parameters.adsorption.A} / {settings.isotherm_parameters.adsorption.B} / {settings.isotherm_parameters.adsorption.C}
                </td>
              </tr>
              <tr>
                <th>desorption A/B/C</th>
                <td className="num">
                  {settings.isotherm_parameters.desorption.A} / {settings.isotherm_parameters.desorption.B} / {settings.isotherm_parameters.desorption.C}
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
