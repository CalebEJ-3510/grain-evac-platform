import { describe, expect, it } from "vitest";
import { initialLadder, LADDER, nextLadderState } from "../lib/alert-ladder";

const hour = 60 * 60 * 1000;

describe("Alert ladder hysteresis and dwell", () => {
  it("does not escalate Watch on a single noisy tick", () => {
    const t0 = 1_000_000;
    let s = initialLadder(10, t0);
    s = nextLadderState(s, 30, t0 + 60_000);
    expect(s.currentBand).toBe("Normal");
    expect(s.candidateBand).toBe("Watch");
  });

  it("escalates Watch after 3h dwell", () => {
    const t0 = 1_000_000;
    let s = initialLadder(10, t0);
    s = nextLadderState(s, 30, t0 + 1_000);
    s = nextLadderState(s, 30, t0 + 1_000 + LADDER.dwellWatchHours * hour);
    expect(s.currentBand).toBe("Watch");
  });

  it("holds Critical until 10-point hysteresis and 6h de-escalation dwell", () => {
    const t0 = 1_000_000;
    let s = initialLadder(80, t0);
    s = nextLadderState(s, 70, t0 + hour);
    expect(s.currentBand).toBe("Critical");
    s = nextLadderState(s, 60, t0 + 2 * hour);
    expect(s.currentBand).toBe("Critical");
    s = nextLadderState(s, 60, t0 + LADDER.deescalateHours * hour);
    expect(s.currentBand).toBe("Priority");
  });

  it("jumps to Critical immediately when a safety override fires", () => {
    const t0 = 1_000_000;
    let s = initialLadder(20, t0);
    s = nextLadderState(s, 20, t0 + 1000, true);
    expect(s.currentBand).toBe("Critical");
  });
});
