import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState } from "../../components/EmptyState";
import { api } from "../../lib/api-client";
import { fmtNum } from "../../lib/format";
import { useLive } from "../../state/LiveStore";
import type { NodeDetail } from "../../types";

function isBad(n: NodeDetail) {
  return n.is_suspect || n.is_stale || n.health_state !== "ok";
}

export function NodeHealth() {
  const { t } = useTranslation();
  const { tickId, role, yard, openStack } = useLive();
  const [nodes, setNodes] = useState<NodeDetail[]>([]);
  const [problemsOnly, setProblemsOnly] = useState(false);
  const canMaintain = role === "inspector";

  useEffect(() => {
    api.nodes().then(setNodes).catch(() => setNodes([]));
  }, [tickId]);

  const inspectCount = useMemo(() => (yard?.stacks ?? []).filter((s) => s.needs_inspection).length, [yard]);
  const shown = problemsOnly ? nodes.filter(isBad) : nodes;
  const groups = useMemo(() => {
    const map = new Map<string, NodeDetail[]>();
    for (const n of shown) {
      const list = map.get(n.stack_id) ?? [];
      list.push(n);
      map.set(n.stack_id, list);
    }
    return [...map.entries()].sort((a, b) => {
      const badA = a[1].filter(isBad).length;
      const badB = b[1].filter(isBad).length;
      return badB - badA || a[0].localeCompare(b[0]);
    });
  }, [shown]);

  if (!nodes.length) return <EmptyState>{t("nodes.empty")}</EmptyState>;

  const log = async (n: NodeDetail, action: string) => {
    if (!canMaintain) return;
    await api.maintenance({
      node_id: n.node_id,
      stack_id: n.stack_id,
      action_type: action,
      operator_role: "Quality Inspector",
    });
    setNodes(await api.nodes());
  };

  return (
    <>
      {inspectCount > 0 && <div className="inspect-banner">{t("nodes.inspectBanner", { count: inspectCount })}</div>}
      <section className="panel">
        <h2>{t("nodes.title")}</h2>
        <div className="seg" style={{ marginBottom: 14 }}>
          <button type="button" className={!problemsOnly ? "on" : ""} onClick={() => setProblemsOnly(false)}>
            {t("nodes.all")}
          </button>
          <button type="button" className={problemsOnly ? "on" : ""} onClick={() => setProblemsOnly(true)}>
            {t("nodes.problems")}
          </button>
        </div>
        {groups.map(([sid, list]) => {
          const ok = list.filter((n) => !isBad(n)).length;
          return (
            <div key={sid} className="node-group">
              <h3>
                <button type="button" className="stack-link" onClick={() => openStack(sid)}>
                  {t("nodes.stackGroup", { id: sid, ok, n: list.length })}
                </button>
              </h3>
              <div className="node-grid">
                {list.map((n) => (
                  <article key={n.node_id} className={`node-card${isBad(n) ? " bad" : ""}`}>
                    <strong>
                      {n.node_id} · {n.position}
                    </strong>
                    <div>
                      {n.is_suspect ? t("nodes.suspect") : n.is_stale ? t("nodes.stale") : n.health_state === "ok" ? t("nodes.ok") : t("nodes.lost")}
                    </div>
                    <div className="cap" title={t("nodes.battery")}>
                      <span style={{ width: `${Math.max(0, Math.min(100, ((n.battery_voltage - 3.0) / 0.7) * 100))}%` }} />
                    </div>
                    <div className="num">
                      {fmtNum(n.battery_voltage, 2)} V · ERH {fmtNum(n.erh_observed, 1)}% · {fmtNum(n.temp_observed, 1)}°C
                    </div>
                    {n.suspect_reasons?.length ? <div>{n.suspect_reasons.join(", ")}</div> : null}
                    {canMaintain && (
                      <div className="form-row">
                        <button className="btn" type="button" onClick={() => void log(n, "replace")}>
                          {t("nodes.replace")}
                        </button>
                        <button className="btn ghost" type="button" onClick={() => void log(n, "service")}>
                          {t("nodes.service")}
                        </button>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            </div>
          );
        })}
      </section>
    </>
  );
}
