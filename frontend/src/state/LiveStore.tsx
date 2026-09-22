import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../lib/api-client";
import { loadSnapshot, saveSnapshot } from "../lib/cache";
import { connectYardSocket } from "../lib/ws-client";
import type { DispatchPlan, Role, ScreenId, WsTick, YardOverview } from "../types";

interface LiveState {
  yard: YardOverview | null;
  dispatch: DispatchPlan | null;
  live: boolean;
  lastSynced: string | null;
  fromCache: boolean;
  tickId: number;
  role: Role;
  setRole: (role: Role) => void;
  screen: ScreenId;
  setScreen: (screen: ScreenId) => void;
  selectedStackId: string | null;
  openStack: (id: string) => void;
  alertOpen: boolean;
  setAlertOpen: (open: boolean) => void;
  alertCount: number;
  controlSim: (body: Record<string, unknown>) => Promise<void>;
}

const Ctx = createContext<LiveState | null>(null);

const ROLE_KEY = "grain-role";

export function LiveStore({ children }: { children: ReactNode }) {
  const cached = loadSnapshot();
  const [yard, setYard] = useState<YardOverview | null>(cached?.yard ?? null);
  const [dispatch, setDispatch] = useState<DispatchPlan | null>(cached?.dispatch ?? null);
  const [live, setLive] = useState(false);
  const [lastSynced, setLastSynced] = useState<string | null>(cached?.savedAt ?? null);
  const [fromCache, setFromCache] = useState(!cached ? false : true);
  const [tickId, setTickId] = useState(0);
  const [role, setRoleState] = useState<Role>(() => {
    const r = localStorage.getItem(ROLE_KEY);
    return r === "inspector" || r === "officer" ? r : "supervisor";
  });
  const [screen, setScreen] = useState<ScreenId>("yard");
  const [selectedStackId, setSelectedStackId] = useState<string | null>(null);
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertCount, setAlertCount] = useState(0);

  const applyYard = useCallback((next: YardOverview, plan: DispatchPlan | null | undefined, alerts?: number) => {
    setYard(next);
    if (plan !== undefined) setDispatch(plan);
    setLastSynced(new Date().toISOString());
    setFromCache(false);
    setTickId((n) => n + 1);
    if (typeof alerts === "number") setAlertCount(alerts);
    saveSnapshot(next, plan ?? null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.yard(), api.dispatch(), api.alerts()])
      .then(([y, d, a]) => {
        if (cancelled) return;
        applyYard(y, d, a.active_alerts?.length ?? 0);
      })
      .catch(() => {
        /* offline: keep cache */
      });
    return () => {
      cancelled = true;
    };
  }, [applyYard]);

  useEffect(() => {
    return connectYardSocket(
      (payload) => {
        const msg = payload as WsTick;
        if (msg?.data?.yard) applyYard(msg.data.yard, msg.data.dispatch, msg.data.active_alerts_count);
      },
      setLive
    );
  }, [applyYard]);

  const setRole = (next: Role) => {
    setRoleState(next);
    localStorage.setItem(ROLE_KEY, next);
  };

  const openStack = (id: string) => {
    setSelectedStackId(id);
    setScreen("stack");
  };

  const controlSim = async (body: Record<string, unknown>) => {
    await api.sim(body);
    const y = await api.yard();
    const d = await api.dispatch();
    applyYard(y, d);
  };

  const value = useMemo<LiveState>(
    () => ({
      yard,
      dispatch,
      live,
      lastSynced,
      fromCache: fromCache && !live,
      tickId,
      role,
      setRole,
      screen,
      setScreen,
      selectedStackId,
      openStack,
      alertOpen,
      setAlertOpen,
      alertCount,
      controlSim,
    }),
    [yard, dispatch, live, lastSynced, fromCache, tickId, role, screen, selectedStackId, alertOpen, alertCount]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLive(): LiveState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useLive outside LiveStore");
  return ctx;
}
