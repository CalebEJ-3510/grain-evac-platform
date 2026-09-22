import { useTranslation } from "react-i18next";
import { fmtSimClock } from "../lib/format";
import { useLive } from "../state/LiveStore";
import type { Role, ScreenId } from "../types";

const SCREENS: ScreenId[] = ["yard", "queue", "stack", "nodes", "season", "settings"];

const ICO: Record<ScreenId, string> = {
  yard: "M2 12h20M4 8h16v10H4z",
  queue: "M4 6h16M4 12h16M4 18h10",
  stack: "M4 18h16L12 4z",
  nodes: "M5 12a3 3 0 1 0 0.01 0M19 7a3 3 0 1 0 0.01 0M19 17a3 3 0 1 0 0.01 0M8 12h8M16 9l-5 2M16 15l-5-2",
  season: "M4 18h16M6 14l3-6 3 4 3-8 3 10",
  settings: "M5 7h14M5 12h14M5 17h14",
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, i18n } = useTranslation();
  const { yard, live, fromCache, lastSynced, role, setRole, screen, setScreen, alertCount, setAlertOpen } = useLive();
  const ta = i18n.language === "ta";

  return (
    <div className="app">
      <header className="mast">
        <div className="brand">
          <div className="mark">DPC</div>
          <div>
            <h1>{t("app.title")}</h1>
            <p className="sub">{t("app.yardName")}</p>
          </div>
        </div>
        <div className="instruments">
          <div className="lcd-well">
            <span className="k">{t("status.sim")}</span>
            <span className="v num">
              {fmtSimClock(yard?.sim_time)}
              <em>{yard?.speed_multiplier ?? 1}×</em>
            </span>
          </div>
          <div className={`lcd-well ${yard?.is_raining ? "rain" : ""}`}>
            <span className="k">{yard?.is_raining ? t("status.raining") : t("status.dry")}</span>
            <span className="v num">
              {yard ? `${yard.ambient_temp.toFixed(1)}°C` : "—"}
              <em>{yard ? `${yard.ambient_rh.toFixed(0)}% RH` : ""}</em>
            </span>
          </div>
          <div className={`link-lamp ${live ? "on" : "off"}`} role="status">
            <span className="led" />
            {live ? t("status.live") : t("status.offline")}
          </div>
          <span className="inst-split" aria-hidden />
          <label className="role-ctl">
            <span className="k">{t("status.role")}</span>
            <select value={role} onChange={(e) => setRole(e.target.value as Role)} aria-label={t("status.role")}>
              <option value="supervisor">{t("role.supervisor")}</option>
              <option value="inspector">{t("role.inspector")}</option>
              <option value="officer">{t("role.officer")}</option>
            </select>
          </label>
          <div className="lang-switch" role="group" aria-label={t("lang.label")}>
            <button type="button" className={!ta ? "on" : ""} onClick={() => void i18n.changeLanguage("en")}>
              EN
            </button>
            <button type="button" className={ta ? "on" : ""} onClick={() => void i18n.changeLanguage("ta")}>
              தமிழ்
            </button>
          </div>
          <button
            className={`alert-bell${alertCount > 0 ? " hot" : ""}`}
            type="button"
            onClick={() => setAlertOpen(true)}
          >
            <span className="k">{t("alerts.bell")}</span>
            <span className="count num">{alertCount}</span>
          </button>
        </div>
      </header>
      <nav className="topnav" aria-label="primary">
        {SCREENS.map((id) => (
          <button key={id} type="button" className={screen === id ? "active" : ""} onClick={() => setScreen(id)}>
            <svg className="nav-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d={ICO[id]} />
            </svg>
            {t(`nav.${id}`)}
          </button>
        ))}
      </nav>
      {fromCache && !live && (
        <div className="offline-banner">
          {t("status.cached")} {lastSynced ? t("status.lastSynced", { time: fmtSimClock(lastSynced) }) : ""}
        </div>
      )}
      {yard?.weather_stale && <div className="stale-banner">{t("status.weatherStale")}</div>}
      <div className={`duty-banner role-${role}`}>
        <strong>{t(`role.${role}`)}</strong>
        <span>{t(`role.brief.${role}`)}</span>
      </div>
      <main className="main">{children}</main>
      <nav className="botnav" aria-label="primary-mobile">
        {SCREENS.map((id) => (
          <button key={id} type="button" className={screen === id ? "active" : ""} onClick={() => setScreen(id)}>
            <svg className="nav-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d={ICO[id]} />
            </svg>
            {t(`nav.${id}`)}
          </button>
        ))}
      </nav>
    </div>
  );
}
