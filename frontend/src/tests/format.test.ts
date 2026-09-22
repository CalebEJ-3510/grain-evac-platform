import { describe, expect, it } from "vitest";
import { isFrontRow } from "../lib/format";

describe("yard row orientation", () => {
  it("puts Row B on the apron and does not treat Back as front", () => {
    expect(isFrontRow("Row-B (Front)")).toBe(true);
    expect(isFrontRow("Row-A (Back)")).toBe(false);
  });
});
