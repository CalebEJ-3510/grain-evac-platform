import { AppShell } from "./components/AppShell";
import { AlertDrawer } from "./components/AlertDrawer";
import { useLive } from "./state/LiveStore";
import { YardPlan } from "./screens/YardPlan/YardPlan";
import { LoadingQueue } from "./screens/LoadingQueue/LoadingQueue";
import { StackDetail } from "./screens/StackDetail/StackDetail";
import { NodeHealth } from "./screens/NodeHealth/NodeHealth";
import { SeasonReport } from "./screens/SeasonReport/SeasonReport";
import { Settings } from "./screens/Settings/Settings";

export function App() {
  const { screen } = useLive();
  return (
    <AppShell>
      <div key={screen} className="stage">
        {screen === "yard" && <YardPlan />}
        {screen === "queue" && <LoadingQueue />}
        {screen === "stack" && <StackDetail />}
        {screen === "nodes" && <NodeHealth />}
        {screen === "season" && <SeasonReport />}
        {screen === "settings" && <Settings />}
      </div>
      <AlertDrawer />
    </AppShell>
  );
}
