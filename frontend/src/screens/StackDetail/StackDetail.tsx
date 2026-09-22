import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BandChip } from "../../components/BandChip";
import { EmptyState } from "../../components/EmptyState";
import { SubIndexBars } from "../../components/SubIndexBars";
import { TrendChart } from "../../components/TrendChart";
import { api } from "../../lib/api-client";
import { fmtNum } from "../../lib/format";
import { useLive } from "../../state/LiveStore";
import type { StackDetail as StackDetailType, VulnerabilityRubric } from "../../types";

export function StackDetail() {
  const { t } = useTranslation();
  const { selectedStackId, tickId, role, yard, openStack } = useLive();
  const [detail, setDetail] = useState<StackDetailType | null>(null);
  const [rubric, setRubric] = useState<VulnerabilityRubric | null>(null);
  const canAudit = role === "inspector";

  useEffect(() => {
    if (!selectedStackId) return;
    api
      .stack(selectedStackId)
      .then((d) => {
        setDetail(d);
        setRubric(d.rubric);
      })
      .catch(() => setDetail(null));
  }, [selectedStackId, tickId]);

  if (!selectedStackId) {
    const stacks = [...(yard?.stacks ?? [])].sort((a, b) => a.stack_id.localeCompare(b.stack_id));
    return (
      <section className="panel">
        <h2>{t("stack.pick")}</h2>
        <div className="pick-grid">
          {stacks.map((s) => (
            <button key={s.stack_id} type="button" className="pick-tile" onClick={() => openStack(s.stack_id)}>
              <strong>{s.stack_id}</strong>
              <span className="num" style={{ color: s.current_epi >= 50 ? "#b42318" : s.current_epi >= 25 ? "#c9891a" : "#1f7a4c" }}>
                {Math.round(s.current_epi)}
              </span>
              <span className="hint">{s.band} · {fmtNum(s.m_est, 1)}% wb</span>
            </button>
          ))}
        </div>
      </section>
    );
  }
  if (!detail || !rubric) return <EmptyState>{t("stack.loading", { id: selectedStackId })}</EmptyState>;

  const s = detail.summary;
  const save = async () => {
    if (!canAudit) return;
    await api.updateRubric(s.stack_id, rubric);
  };

  const epiPct = Math.max(0, Math.min(100, s.current_epi));

  return (
    <>
      <section className="panel">
        <h2>
          {s.stack_id} <BandChip band={s.band} />
        </h2>
        <div className="grid-3">
          <div className="epi-gauge">
            <div className="epi-col">
              <span style={{ height: `${epiPct}%`, background: s.current_epi >= 75 ? "#b42318" : s.current_epi >= 50 ? "#c45c12" : s.current_epi >= 25 ? "#c9891a" : "#1f7a4c" }} />
            </div>
            <div className="n num">{Math.round(s.current_epi)}</div>
            <div className="l">{t("stack.epi")}</div>
          </div>
          <div className="grid-2">
          <div className="metric">
            <div className="k">{t("stack.moisture")}</div>
            <div className="v">{fmtNum(s.m_est, 2)}%</div>
          </div>
          <div className="metric">
            <div className="k">{t("stack.aw")}</div>
            <div className="v">{fmtNum(s.aw_max, 3)}</div>
          </div>
          <div className="metric">
            <div className="k">{t("stack.core")}</div>
            <div className="v">{fmtNum(s.t_core, 1)}°C</div>
          </div>
          <div className="metric">
            <div className="k">{t("stack.rate")}</div>
            <div className="v">{fmtNum(s.dm_dt_24h, 3)} %/d</div>
          </div>
          <div className="metric">
            <div className="k">{t("stack.age")}</div>
            <div className="v">{fmtNum(s.age_days, 0)} d</div>
          </div>
          <div className="metric">
            <div className="k">{t("stack.nodesOk")}</div>
            <div className="v">{s.n_ok}</div>
          </div>
          </div>
        </div>
        <p>
          {t("stack.branch")}: {s.active_branch} · {t("stack.scenario")}: {t(`settings.scenarios.${s.assigned_scenario}`, { defaultValue: s.assigned_scenario })}
        </p>
      </section>
      <section className="panel">
        <h3>{t("stack.trend")}</h3>
        <TrendChart history={detail.recent_history} />
      </section>
      <section className="panel">
        <h3>{t("stack.sub")}</h3>
        <SubIndexBars values={detail.sub_index_breakdown} />
      </section>
      <section className="panel">
        <h3>
          {t("stack.rubric")} · {fmtNum(s.vulnerability_score, 2)}
        </h3>
        <RubricEditor rubric={rubric} setRubric={setRubric} disabled={!canAudit} />
        <button className="btn" type="button" disabled={!canAudit} onClick={() => void save()}>
          {t("stack.saveAudit")}
        </button>
        {!canAudit && <p className="hint">{t("role.readonly")}</p>}
      </section>
      <section className="panel">
        <h3>{t("nav.nodes")}</h3>
        <div className="node-grid">
        {detail.nodes.map((n) => (
          <div key={n.node_id} className={`node-card${n.is_suspect || n.is_stale ? " bad" : ""}`}>
            <strong>{n.node_id}</strong> · {n.position} · {n.is_suspect ? t("nodes.suspect") : n.is_stale ? t("nodes.stale") : n.health_state === "ok" ? t("nodes.ok") : t("nodes.lost")}
            <div className="num">
              ERH {fmtNum(n.erh_observed, 1)}% · T {fmtNum(n.temp_observed, 1)}°C · core {fmtNum(n.temp_core_observed, 1)}°C · {fmtNum(n.battery_voltage, 2)} V
            </div>
            {n.suspect_reasons?.length ? <div>{n.suspect_reasons.join(", ")}</div> : null}
          </div>
        ))}
        </div>
      </section>
    </>
  );
}

function RubricEditor({
  rubric,
  setRubric,
  disabled,
}: {
  rubric: VulnerabilityRubric;
  setRubric: (r: VulnerabilityRubric) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const fields: Array<{ key: keyof VulnerabilityRubric; label: string; opts: [string, string, string] }> = [
    { key: "tarpaulin_condition", label: t("stack.tarpaulin"), opts: [t("stack.tarp0"), t("stack.tarp1"), t("stack.tarp2")] },
    { key: "dunnage_plinth", label: t("stack.dunnage"), opts: [t("stack.dun0"), t("stack.dun1"), t("stack.dun2")] },
    { key: "drainage_proximity", label: t("stack.drainage"), opts: [t("stack.dra0"), t("stack.dra1"), t("stack.dra2")] },
    { key: "position_in_row", label: t("stack.position"), opts: [t("stack.pos0"), t("stack.pos1"), t("stack.pos2")] },
    { key: "residence_time", label: t("stack.residence"), opts: [t("stack.res0"), t("stack.res1"), t("stack.res2")] },
  ];
  return (
    <>
      {fields.map((f) => (
        <div key={f.key} style={{ marginBottom: 10 }}>
          <div className="k">{f.label}</div>
          <div className="seg">
            {f.opts.map((label, i) => (
              <button
                key={label}
                type="button"
                className={rubric[f.key] === i ? "on" : ""}
                disabled={disabled}
                onClick={() => setRubric({ ...rubric, [f.key]: i })}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      ))}
    </>
  );
}
