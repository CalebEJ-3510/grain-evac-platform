import { BAND_FILL, BAND_INK, type BandName } from "../design-tokens";
import type { Band } from "../types";

export type { Band };

export const BANDS: Band[] = ["Normal", "Watch", "Priority", "Critical"];

export function normalizeBand(value: string | undefined | null): Band {
  if (value === "Watch" || value === "Priority" || value === "Critical") return value;
  return "Normal";
}

export function bandFromEpi(epi: number): Band {
  if (epi >= 75) return "Critical";
  if (epi >= 50) return "Priority";
  if (epi >= 25) return "Watch";
  return "Normal";
}

export function bandFill(band: string): string {
  return BAND_FILL[normalizeBand(band) as BandName];
}

export function bandInk(band: string): string {
  return BAND_INK[normalizeBand(band) as BandName];
}

export function bandAction(band: Band): { en: string; ta: string } {
  switch (band) {
    case "Critical":
      return { en: "Load within 24 h; inspect immediately", ta: "24 மணிநேரத்தில் ஏற்றுக; உடனே ஆய்வு செய்க" };
    case "Priority":
      return { en: "Load within 48 h; verify tarpaulin now", ta: "48 மணிநேரத்தில் ஏற்றுக; தற்போது தார்பாலினை சரிபார்க்க" };
    case "Watch":
      return { en: "Include in next dry-weather movement", ta: "அடுத்த வறண்ட கால இயக்கத்தில் சேர்க்க" };
    default:
      return { en: "Routine", ta: "வழக்கம்" };
  }
}
