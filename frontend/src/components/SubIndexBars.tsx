import { useTranslation } from "react-i18next";
import { TOKENS } from "../design-tokens";

const KEYS = ["s_M", "s_R", "s_T", "s_A", "s_F", "s_V"] as const;

export function SubIndexBars({ values }: { values: Record<string, number> }) {
  const { t } = useTranslation();
  return (
    <div>
      {KEYS.map((k) => {
        const v = Math.max(0, Math.min(1, Number(values[k] ?? 0)));
        return (
          <div key={k} style={{ display: "grid", gridTemplateColumns: "110px 1fr 42px", gap: 8, alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: 12 }}>{t(`sub.${k}`)}</span>
            <div style={{ height: 10, background: "#d5e0d8", border: `1px solid ${TOKENS.tarpShade}` }}>
              <span style={{ display: "block", height: "100%", width: `${v * 100}%`, background: v >= 0.75 ? TOKENS.hazardTape : v >= 0.5 ? TOKENS.priorityOchre : TOKENS.tarpField, transition: "width 0.6s ease" }} />
            </div>
            <span className="num" style={{ fontSize: 12, fontWeight: 650 }}>
              {v.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
