import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api-client";
import { fmtSimClock } from "../lib/format";
import { useLive } from "../state/LiveStore";
import type { AlertsPayload } from "../types";
import { BandChip } from "./BandChip";
import { EmptyState } from "./EmptyState";

export function AlertDrawer() {
  const { t, i18n } = useTranslation();
  const { alertOpen, setAlertOpen, tickId } = useLive();
  const [data, setData] = useState<AlertsPayload | null>(null);

  useEffect(() => {
    if (!alertOpen) return;
    api.alerts().then(setData).catch(() => setData(null));
  }, [alertOpen, tickId]);

  if (!alertOpen) return null;

  return (
    <div className="drawer" onClick={() => setAlertOpen(false)} role="presentation">
      <aside className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={t("alerts.title")}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>{t("alerts.title")}</h2>
          <button className="btn ghost" type="button" onClick={() => setAlertOpen(false)}>
            {t("alerts.close")}
          </button>
        </div>
        {!data?.active_alerts?.length ? (
          <EmptyState>{t("alerts.none")}</EmptyState>
        ) : (
          data.active_alerts.map((a) => (
            <div key={a.alert_id} className="sms">
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <strong>{a.stack_id}</strong>
                <BandChip band={a.band} />
              </div>
              <p>{i18n.language === "ta" ? a.reason_ta : a.reason_en}</p>
              <small>
                {fmtSimClock(a.triggered_at)} · {a.dwell_satisfied ? t("alerts.dwell") : t("alerts.pending")}
                {a.driving_node_ids?.length ? ` · ${a.driving_node_ids.join(", ")}` : ""}
              </small>
            </div>
          ))
        )}
        <h3 style={{ fontSize: 14 }}>{t("alerts.sms")}</h3>
        {data?.simulated_sms_inbox?.map((m) => (
          <div key={m.alert_id + m.timestamp} className="sms">
            <strong>{m.stack_id}</strong>
            <p>{i18n.language === "ta" ? m.sms_body_ta : m.sms_body_en}</p>
            <small>
              {m.recipient} · {fmtSimClock(m.timestamp)}
            </small>
          </div>
        ))}
      </aside>
    </div>
  );
}
