import { describe, expect, it } from "vitest";
import { BAND_FILL } from "../design-tokens";
import { bandFill, bandFromEpi, normalizeBand } from "../lib/bands";

describe("Yard Plan band coloring", () => {
  it("maps EPI thresholds to operational bands", () => {
    expect(bandFromEpi(0)).toBe("Normal");
    expect(bandFromEpi(24.9)).toBe("Normal");
    expect(bandFromEpi(25)).toBe("Watch");
    expect(bandFromEpi(49.9)).toBe("Watch");
    expect(bandFromEpi(50)).toBe("Priority");
    expect(bandFromEpi(74.9)).toBe("Priority");
    expect(bandFromEpi(75)).toBe("Critical");
    expect(bandFromEpi(100)).toBe("Critical");
  });

  it("uses tarpaulin green for Normal and hazard tape for Critical", () => {
    expect(bandFill("Normal")).toBe(BAND_FILL.Normal);
    expect(bandFill("Critical")).toBe(BAND_FILL.Critical);
    expect(bandFill("unknown")).toBe(BAND_FILL.Normal);
    expect(normalizeBand("Priority")).toBe("Priority");
  });
});
