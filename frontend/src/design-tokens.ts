/** Domain-grounded tokens. Hex values are also declared in index.css. */
export const TOKENS = {
  tarpShade: "#0C2F24",
  tarpField: "#176B45",
  paddyCanopy: "#1F7A4C",
  wetSlab: "#C5D0C8",
  clipboard: "#F1F6F2",
  ink: "#0D1F18",
  mute: "#3E574B",
  rule: "#7A9588",
  roadPaint: "#C9891A",
  priorityOchre: "#C45C12",
  hazardTape: "#B42318",
  lcd: "#D7E8D4",
} as const;

export const BAND_FILL = {
  Normal: "#1F7A4C",
  Watch: "#C9891A",
  Priority: "#C45C12",
  Critical: "#B42318",
} as const;

export const BAND_INK = {
  Normal: "#F1F6F2",
  Watch: "#1A1204",
  Priority: "#FFF6EE",
  Critical: "#FFF5F4",
} as const;

export type BandName = keyof typeof BAND_FILL;
