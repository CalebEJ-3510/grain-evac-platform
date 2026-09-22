import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { EmptyState } from "../../components/EmptyState";
import { bandFill } from "../../lib/bands";
import { api } from "../../lib/api-client";
import { fmtNum } from "../../lib/format";
import { useLive } from "../../state/LiveStore";
import type { SeasonReport as SeasonReportType } from "../../types";

export function SeasonReport() {
  const { t } = useTranslation();
  const { tickId } = useLive();
  const [data, setData] = useState<SeasonReportType | null>(null);

  useEffect(() => {
    api.season().then(setData).catch(() => setData(null));
  }, [tickId]);

  if (!data) return <EmptyState>{t("season.empty")}</EmptyState>;

  const bands = Object.entries(data.tonnes_by_band ?? {});
  const max = Math.max(1, ...bands.map(([, v]) => Number(v)));

  return (
    <>
      <section className="rail">
        <div>
          <div className="k">{t("season.evacuated")}</div>
          <div className="v num">{fmtNum(data.total_tonnes_evacuated, 0)} MT</div>
        </div>
        <div>
          <div className="k">{t("season.avoided")}</div>
          <div className="v num">{data.avoided_breaches_count}</div>
        </div>
        <div>
          <div className="k">{t("season.lead")}</div>
          <div className="v num">{fmtNum(data.average_lead_time_hours, 1)} h</div>
        </div>
        <div>
          <div className="k">{t("season.survival")}</div>
          <div className="v num">{fmtNum(data.node_survival_rate_percent, 1)}%</div>
        </div>
      </section>
      <section className="panel">
        <h2>{t("season.byBand")}</h2>
        {bands.map(([band, tonnes]) => (
          <div key={band} style={{ display: "grid", gridTemplateColumns: "90px 1fr 70px", gap: 8, alignItems: "center", marginBottom: 8 }}>
            <span>{t(`band.${band}`, { defaultValue: band })}</span>
            <div className="cap">
              <span style={{ width: `${(Number(tonnes) / max) * 100}%`, background: bandFill(band) }} />
            </div>
            <span className="num">{fmtNum(Number(tonnes), 0)} MT</span>
          </div>
        ))}
        <div className="grid-2" style={{ marginTop: 12 }}>
          <div className="metric">
            <div className="k">{t("season.precision")}</div>
            <div className="v">{fmtNum(data.precision_at_6, 2)}</div>
          </div>
          <div className="metric">
            <div className="k">{t("season.opt")}</div>
            <div className="v">{fmtNum(data.optimization_improvement_gain, 2)}</div>
          </div>
        </div>
        {!data.evacuated_stacks?.length && <p className="hint">{t("season.empty")}</p>}
      </section>
    </>
  );
}
