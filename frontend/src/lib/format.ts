export function fmtNum(value: number, digits = 1): string {
  if (!Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

export function fmtEpi(value: number): string {
  if (!Number.isFinite(value)) return "—";
  return Math.round(value).toString();
}

export function fmtSimClock(iso: string | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

export function fmtHours(hours: number | null | undefined, t: (key: string, opts?: Record<string, unknown>) => string): string {
  if (hours == null || !Number.isFinite(hours)) return t("time.stable");
  if (hours <= 0) return t("time.now");
  if (hours < 24) return t("time.h", { n: fmtNum(hours, 0) });
  return t("time.d", { n: fmtNum(hours / 24, 1) });
}

export function isFrontRow(rowId: string): boolean {
  return /row[\s-]*b|front/i.test(rowId);
}
