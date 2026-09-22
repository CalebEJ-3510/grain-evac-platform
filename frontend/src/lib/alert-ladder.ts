import { bandFromEpi, type Band } from "./bands";

export const LADDER = {
  watch: 25,
  priority: 50,
  critical: 75,
  hysteresis: 10,
  dwellWatchHours: 3,
  dwellPriorityHours: 2,
  dwellCriticalMinutes: 30,
  deescalateHours: 6,
} as const;

export interface LadderState {
  currentBand: Band;
  bandEnteredAt: number;
  candidateBand: Band | null;
  candidateStartedAt: number | null;
}

function dwellMsFor(band: Band): number {
  if (band === "Critical") return LADDER.dwellCriticalMinutes * 60 * 1000;
  if (band === "Priority") return LADDER.dwellPriorityHours * 60 * 60 * 1000;
  if (band === "Watch") return LADDER.dwellWatchHours * 60 * 60 * 1000;
  return 0;
}

const RANK: Record<Band, number> = { Normal: 0, Watch: 1, Priority: 2, Critical: 3 };

export function nextLadderState(
  prev: LadderState,
  epi: number,
  nowMs: number,
  overrideFired = false
): LadderState {
  const observed = overrideFired ? "Critical" : bandFromEpi(epi);
  if (RANK[observed] > RANK[prev.currentBand]) {
    if (overrideFired) {
      return {
        currentBand: "Critical",
        bandEnteredAt: nowMs,
        candidateBand: null,
        candidateStartedAt: null,
      };
    }
    if (prev.candidateBand !== observed) {
      return { ...prev, candidateBand: observed, candidateStartedAt: nowMs };
    }
    const started = prev.candidateStartedAt ?? nowMs;
    if (nowMs - started >= dwellMsFor(observed) || overrideFired) {
      return {
        currentBand: observed,
        bandEnteredAt: nowMs,
        candidateBand: null,
        candidateStartedAt: null,
      };
    }
    return prev;
  }

  if (RANK[observed] < RANK[prev.currentBand]) {
    const exitLine =
      prev.currentBand === "Critical"
        ? LADDER.critical - LADDER.hysteresis
        : prev.currentBand === "Priority"
          ? LADDER.priority - LADDER.hysteresis
          : prev.currentBand === "Watch"
            ? LADDER.watch - LADDER.hysteresis
            : 0;
    if (epi >= exitLine && !overrideFired) return { ...prev, candidateBand: null, candidateStartedAt: null };
    if (nowMs - prev.bandEnteredAt < LADDER.deescalateHours * 60 * 60 * 1000) {
      return { ...prev, candidateBand: observed, candidateStartedAt: prev.candidateStartedAt ?? nowMs };
    }
    return {
      currentBand: observed,
      bandEnteredAt: nowMs,
      candidateBand: null,
      candidateStartedAt: null,
    };
  }

  return { ...prev, candidateBand: null, candidateStartedAt: null };
}

export function initialLadder(epi: number, nowMs: number): LadderState {
  return { currentBand: bandFromEpi(epi), bandEnteredAt: nowMs, candidateBand: null, candidateStartedAt: null };
}
