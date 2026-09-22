export function capacityFill(loadedMt: number, allocatedMt: number): number {
  if (!Number.isFinite(loadedMt) || !Number.isFinite(allocatedMt) || allocatedMt <= 0) return 0;
  return Math.max(0, Math.min(1, loadedMt / allocatedMt));
}

export function remainingCapacity(loadedMt: number, allocatedMt: number): number {
  if (!Number.isFinite(loadedMt) || !Number.isFinite(allocatedMt)) return 0;
  return Math.max(0, allocatedMt - loadedMt);
}
