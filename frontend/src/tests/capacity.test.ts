import { describe, expect, it } from "vitest";
import { capacityFill, remainingCapacity } from "../lib/capacity";

describe("Loading Queue capacity bar", () => {
  it("fills against today's allotment and never exceeds 1.0 for the bar", () => {
    expect(capacityFill(96, 120)).toBeCloseTo(0.8);
    expect(capacityFill(120, 120)).toBe(1);
    expect(capacityFill(150, 120)).toBe(1);
    expect(capacityFill(0, 120)).toBe(0);
    expect(capacityFill(10, 0)).toBe(0);
  });

  it("reports remaining open tonnes", () => {
    expect(remainingCapacity(96, 120)).toBe(24);
    expect(remainingCapacity(130, 120)).toBe(0);
  });
});
