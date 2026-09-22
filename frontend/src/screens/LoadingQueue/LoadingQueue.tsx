import { useState } from "react";
import { useTranslation } from "react-i18next";
import { BandChip } from "../../components/BandChip";
import { EmptyState } from "../../components/EmptyState";
import { api } from "../../lib/api-client";
import { capacityFill, remainingCapacity } from "../../lib/capacity";
import { fmtEpi, fmtHours, fmtNum } from "../../lib/format";
import { useLive } from "../../state/LiveStore";

const CODES = ["VISUAL_TARPAULIN_DEFECT", "ACCESS_OBSTRUCTION", "TRUCK_AVAILABILITY"] as const;

export function LoadingQueue() {
  const { t, i18n } = useTranslation();
  const { dispatch, role, openStack } = useLive();
  const [code, setCode] = useState<(typeof CODES)[number]>("VISUAL_TARPAULIN_DEFECT");
  const [busy, setBusy] = useState<string | null>(null);
  const canAct = role === "supervisor";
  const loaded = dispatch?.total_loaded_mt ?? 0;
  const alloc = dispatch?.allocated_capacity_mt ?? 120;
  const fill = capacityFill(loaded, alloc);
  const left = remainingCapacity(loaded, alloc);
  const queue = dispatch?.queue ?? [];

  const override = async (stackId: string) => {
    if (!canAct) return;
    setBusy(stackId);
    try {
      await api.override(stackId, code);
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="panel">
      <h2>{t("queue.title")}</h2>
      <div className="k">
        {t("queue.allotment")}: {t("queue.loaded", { loaded: fmtNum(loaded, 0), alloc: fmtNum(alloc, 0) })}
      </div>
      <div className="cap" role="meter" aria-valuenow={Math.round(fill * 100)} aria-valuemin={0} aria-valuemax={100}>
        <span style={{ width: `${fill * 100}%` }} />
      </div>
      <p className="hint">{fill > 1 ? t("queue.over") : t("queue.remaining", { mt: fmtNum(left, 0) })}</p>
      {canAct && (
        <label className="k" style={{ display: "grid", gap: 6, marginBottom: 8, maxWidth: 320 }}>
          {t("queue.overrideReason")}
          <select value={code} onChange={(e) => setCode(e.target.value as (typeof CODES)[number])}>
            {CODES.map((c) => (
              <option key={c} value={c}>
                {t(`queue.codes.${c}`)}
              </option>
            ))}
          </select>
        </label>
      )}
      {!queue.length && <EmptyState>{t("queue.empty")}</EmptyState>}
      {queue.map((item) => (
        <article key={item.stack_id} className="queue-item">
          <div className="ord num">{item.loading_order}</div>
          <div>
            <button type="button" className="stack-link" onClick={() => openStack(item.stack_id)}>
              {item.stack_id} · {t("queue.truck", { n: item.truck_number })}
            </button>
            <div>
              <BandChip band={item.band} />{" "}
              <span className="num">
                {t("queue.epiLine", {
                  epi: fmtEpi(item.epi_score),
                  mt: fmtNum(item.tonnage_mt, 0),
                  breach: fmtHours(item.hours_to_breach, t),
                })}
              </span>
            </div>
            <p>
              {t("queue.reason")}: {i18n.language === "ta" ? item.reason_ta : item.reason_en}
            </p>
            {item.is_blocked && <p>{t("queue.blockedBy", { id: item.blocked_by })}</p>}
          </div>
          <button className="btn" type="button" disabled={!canAct || busy === item.stack_id} onClick={() => void override(item.stack_id)}>
            {t("queue.override")}
          </button>
        </article>
      ))}
    </section>
  );
}
