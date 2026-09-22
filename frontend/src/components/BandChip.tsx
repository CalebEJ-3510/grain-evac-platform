import { useTranslation } from "react-i18next";
import { bandFill, bandInk, normalizeBand } from "../lib/bands";

export function BandChip({ band }: { band: string }) {
  const { t } = useTranslation();
  const b = normalizeBand(band);
  return (
    <span
      className="num"
      style={{
        display: "inline-block",
        padding: "2px 8px",
        background: bandFill(b),
        color: bandInk(b),
        fontSize: 12,
        fontWeight: 700,
      }}
    >
      {t(`band.${b}`, { defaultValue: b })}
    </span>
  );
}
