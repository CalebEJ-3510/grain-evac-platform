import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { TOKENS } from "../design-tokens";

interface Point {
  ts: string;
  m_est: number;
  aw_max: number;
  t_core: number;
}

function asPoints(history: Array<Record<string, unknown>>): Point[] {
  return history
    .map((row) => ({
      ts: String(row.ts ?? ""),
      m_est: Number(row.m_est ?? 0),
      aw_max: Number(row.aw_max ?? 0),
      t_core: Number(row.t_core ?? 0),
    }))
    .filter((p) => p.ts);
}

function path(xs: number[], ys: number[], w: number, h: number, min: number, max: number): string {
  if (!xs.length) return "";
  const span = Math.max(1e-6, max - min);
  return xs
    .map((x, i) => {
      const px = (x / Math.max(1, xs.length - 1)) * w;
      const py = h - ((ys[i] - min) / span) * h;
      return `${i === 0 ? "M" : "L"}${px.toFixed(1)},${py.toFixed(1)}`;
    })
    .join(" ");
}

export function TrendChart({ history }: { history: Array<Record<string, unknown>> }) {
  const { t } = useTranslation();
  const pts = useMemo(() => asPoints(history), [history]);
  const w = 640;
  const h = 160;
  const xs = pts.map((_, i) => i);
  const m = pts.map((p) => p.m_est);
  const aw = pts.map((p) => p.aw_max * 20);
  const tcore = pts.map((p) => p.t_core);
  const mPath = path(xs, m, w, h, 12, 18);
  const awPath = path(xs, aw, w, h, 12, 18);
  const tPath = path(xs, tcore, w, h, 20, 45);
  const y17 = h - ((17 - 12) / 6) * h;
  const y065 = h - ((0.65 * 20 - 12) / 6) * h;

  return (
    <div>
      <svg className="chart" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={t("stack.trend")}>
        <line x1="0" y1={y17} x2={w} y2={y17} stroke={TOKENS.hazardTape} strokeDasharray="4 3" />
        <line x1="0" y1={y065} x2={w} y2={y065} stroke={TOKENS.roadPaint} strokeDasharray="2 3" />
        <path d={mPath} fill="none" stroke={TOKENS.tarpField} strokeWidth="2.4" />
        <path d={awPath} fill="none" stroke={TOKENS.mute} strokeWidth="1.6" />
        <path d={tPath} fill="none" stroke={TOKENS.priorityOchre} strokeWidth="1.6" />
      </svg>
      <div className="legend">
        <span style={{ color: TOKENS.tarpField }}>M_est</span>
        <span style={{ color: TOKENS.mute }}>a_w × 20</span>
        <span style={{ color: TOKENS.priorityOchre }}>T_core</span>
        <span style={{ color: TOKENS.hazardTape }}>{t("stack.m17")}</span>
        <span style={{ color: TOKENS.roadPaint }}>{t("stack.aw065")}</span>
      </div>
    </div>
  );
}
