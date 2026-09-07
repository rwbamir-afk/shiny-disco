import { useEffect, useState } from "react";
import { useSession } from "./state/session";
import { notifyReady } from "./lib/telegram";
import { Home } from "./pages/Home";
import { Room } from "./pages/Room";
import { GameTable } from "./pages/GameTable";
import { ResultScreen } from "./pages/Result";
import { Profile } from "./pages/Profile";
import { Ranking } from "./pages/Ranking";
import { Economy } from "./pages/Economy";
import { Progression } from "./pages/Progression";
import { Social } from "./pages/Social";
import { Settings } from "./pages/Settings";
import { Clubs } from "./pages/Clubs";
import { Tournaments } from "./pages/Tournaments";
import { Premium } from "./pages/Premium";

type ScreenName = "home" | "room" | "game" | "result" | "profile" | "ranking" | "economy" | "progression" | "social" | "settings" | "clubs" | "tournaments" | "premium";
type Route = { name: ScreenName; gameId?: string; team?: "A" | "B" };
export type Navigate = (name: ScreenName, params?: Partial<Route>) => void;

export default function App() {
  const { session, loading, error, authenticate } = useSession();
  const [route, setRoute] = useState<Route>({ name: "home" });
  const navigate: Navigate = (name, params) => setRoute({ name, ...params });

  useEffect(() => {
    notifyReady();
  }, []);

  if (!session) {
    return (
      <div className="app col center pad" style={{ justifyContent: "center", minHeight: "100vh" }}>
        <h1 className="display">حکم</h1>
        {loading ? (
          <div className="spinner" />
        ) : (
          <button className="btn primary block" onClick={() => void authenticate()}>
            ورود با تلگرام
          </button>
        )}
        {error && <div className="status error mt">{error}</div>}
      </div>
    );
  }

  switch (route.name) {
    case "game":
      return <GameTable gameId={route.gameId!} navigate={navigate} />;
    case "result":
      return <ResultScreen gameId={route.gameId!} team={route.team ?? "A"} navigate={navigate} />;
    case "room":
      return <Room navigate={navigate} />;
    case "profile":
      return <Profile navigate={navigate} />;
    case "ranking":
      return <Ranking navigate={navigate} />;
    case "economy":
      return <Economy navigate={navigate} />;
    case "progression":
      return <Progression navigate={navigate} />;
    case "social":
      return <Social navigate={navigate} />;
    case "settings":
      return <Settings navigate={navigate} />;
    case "clubs":
      return <Clubs navigate={navigate} />;
    case "tournaments":
      return <Tournaments navigate={navigate} />;
    case "premium":
      return <Premium navigate={navigate} />;
    default:
      return <Home navigate={navigate} />;
  }
}
