import type { DispatchPlan, YardOverview } from "../types";

const KEY = "grain-evac-last-sync";

export interface CachedSnapshot {
  yard: YardOverview;
  dispatch: DispatchPlan | null;
  savedAt: string;
}

export function saveSnapshot(yard: YardOverview, dispatch: DispatchPlan | null): void {
  const payload: CachedSnapshot = { yard, dispatch, savedAt: new Date().toISOString() };
  try {
    localStorage.setItem(KEY, JSON.stringify(payload));
  } catch {
    /* quota / private mode */
  }
}

export function loadSnapshot(): CachedSnapshot | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    return JSON.parse(raw) as CachedSnapshot;
  } catch {
    return null;
  }
}
