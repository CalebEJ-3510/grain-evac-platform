import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { bandFill, normalizeBand } from "../../lib/bands";
import { fmtEpi, fmtNum, isFrontRow } from "../../lib/format";
import { useLive } from "../../state/LiveStore";
import type { StackSummary } from "../../types";
import { EmptyState } from "../../components/EmptyState";

function KpiRail() {
  const { t } = useTranslation();
  const { yard, dispatch } = useLive();
  const active = (yard?.stacks ?? []).filter((s) => !s.is_evacuated);
  const tonnes = active.reduce((n, s) => n + s.tonnage_mt, 0);
  const alloc = dispatch?.allocated_capacity_mt ?? 120;
  return (
    <section className="rail" aria-label="yard instruments">
      <div>
        <div className="k">{t("kpi.weighbridge")}</div>
        <div className="v num">{fmtNum(alloc, 0)} MT</div>
        <div className="hint">{t("kpi.perDay")}</div>
      </div>
      <div>
        <div className="k">{t("kpi.storage")}</div>
        <div className="v num">{fmtNum(tonnes, 0)} MT</div>
        <div className="hint">{t("kpi.stacks", { count: active.length })}</div>
      </div>
      <div>
        <div className="k">{t("kpi.atRisk")}</div>
        <div className={`v num ${yard && yard.at_risk_count > 0 ? "danger" : ""}`}>{yard?.at_risk_count ?? 0}</div>
      </div>
      <div>
        <div className="k">{t("kpi.weather")}</div>
        <div className="v num" style={{ fontSize: 20 }}>
          {yard ? `${yard.ambient_temp.toFixed(1)}°C` : "—"}
        </div>
        <div className="hint">
          {yard ? `${yard.ambient_rh.toFixed(0)}% RH · R72 ${fmtNum(yard.r72_mm, 0)} mm` : ""}
        </div>
      </div>
    </section>
  );
}

function moistureWidth(mEst: number): number {
  return Math.max(4, Math.min(100, ((mEst - 12) / 6) * 100));
}

function Tile({ stack, prevEpi, onOpen }: { stack: StackSummary; prevEpi?: number; onOpen: () => void }) {
  const { t } = useTranslation();
  const band = normalizeBand(stack.band);
  const fill = bandFill(band);
  const pulse = prevEpi != null && bandChanged(prevEpi, stack.current_epi);
  return (
    <button
      type="button"
      className={`stack-tile${pulse ? " pulse" : ""}${stack.is_evacuated ? " evac" : ""}`}
      onClick={onOpen}
    >
      <span className="band" style={{ background: fill }} />
      <span className="body">
        <span className="id">{stack.stack_id}</span>
        <span className="epi num" style={{ color: fill }}>
          {fmtEpi(stack.current_epi)}
        </span>
        <span className="meta">
          {fmtNum(stack.tonnage_mt, 0)} MT · {stack.n_ok} nodes
          <br />
          {fmtNum(stack.m_est, 2)}% wb
        </span>
        <span className="moist" title={`${fmtNum(stack.m_est, 2)}% wb`}>
          <span style={{ width: `${moistureWidth(stack.m_est)}%`, background: fill }} />
        </span>
        {stack.is_evacuated && <span className="flag muted">{t("yard.evacuated")}</span>}
        {!stack.is_evacuated && stack.blocked_by_stack_id && (
          <span className="flag muted">{t("yard.blocked")} · {stack.blocked_by_stack_id}</span>
        )}
        {stack.needs_inspection && <span className="flag">{t("yard.inspect")}</span>}
      </span>
    </button>
  );
}

function bandChanged(prev: number, next: number): boolean {
  const cut = [25, 50, 75];
  return cut.some((c) => (prev < c && next >= c) || (prev >= c && next < c));
}

export function YardPlan() {
  const { t } = useTranslation();
  const { yard, openStack } = useLive();
  const prev = useRef<Record<string, number>>({});
  const [flash, setFlash] = useState<Record<string, number>>({});

  useEffect(() => {
    const map: Record<string, number> = {};
    for (const s of yard?.stacks ?? []) map[s.stack_id] = s.current_epi;
    setFlash({ ...prev.current });
    prev.current = map;
  }, [yard]);

  const stacks = yard?.stacks ?? [];
  if (!stacks.length) return <EmptyState>{t("yard.empty")}</EmptyState>;

  const back = stacks.filter((s) => !isFrontRow(s.row_id)).sort((a, b) => a.position_index - b.position_index);
  const front = stacks.filter((s) => isFrontRow(s.row_id)).sort((a, b) => a.position_index - b.position_index);

  return (
    <>
      <KpiRail />
      <section className="plan">
        <div className="ditch">{t("yard.north")}</div>
        <div className="row-label">{t("yard.rowA")}</div>
        <div className="stack-row">
          {back.map((s) => (
            <Tile key={s.stack_id} stack={s} prevEpi={flash[s.stack_id]} onOpen={() => openStack(s.stack_id)} />
          ))}
        </div>
        <div className="aisle">{t("yard.aisle")}</div>
        <div className="row-label">{t("yard.rowB")}</div>
        <div className="stack-row">
          {front.map((s) => (
            <Tile key={s.stack_id} stack={s} prevEpi={flash[s.stack_id]} onOpen={() => openStack(s.stack_id)} />
          ))}
        </div>
        <div className="bay">
          <div>
            <h2>{t("yard.bay")}</h2>
            <p>{t("yard.bayMeta")}</p>
          </div>
          <p>{t("app.tapInspect")}</p>
        </div>
      </section>
    </>
  );
}
