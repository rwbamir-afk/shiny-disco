import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Profile, Result } from "../lib/contracts";
import type { Navigate } from "../App";

export function ResultScreen({ gameId, team, navigate }: { gameId: string; team: "A" | "B"; navigate: Navigate }) {
  const { accessToken } = useSession();
  const [result, setResult] = useState<Result | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api<Result>(`/api/v1/games/${gameId}/result`, { token: accessToken });
        setResult(r);
        const me = await api<{ profile: Profile }>("/api/v1/users/me", { token: accessToken });
        setProfile(me.profile);
      } catch (e) {
        setError(e instanceof Error ? e.message : "خطا در دریافت نتیجه");
      }
    })();
  }, [gameId, accessToken]);

  const won = result?.winner_team === team;

  return (
    <div className="app pad col center">
      <h1 className="display">{won ? "بردی!" : "باختی"}</h1>
      {result && (
        <div className="panel pad col center mt" style={{ width: "100%" }}>
          <div className="row center" style={{ justifyContent: "space-around", width: "100%" }}>
            <div className="col center">
              <span className="section-title">تیم شما</span>
              <span className="display">{result.scores.A}</span>
            </div>
            <span className="section-title">–</span>
            <div className="col center">
              <span className="section-title">حریف</span>
              <span className="display">{result.scores.B}</span>
            </div>
          </div>
          <hr className="divider" />
          {profile && (
            <div className="row" style={{ justifyContent: "space-around", width: "100%" }}>
              <div className="col center">
                <span className="section-title">امتیاز</span>
                <span>{profile.rating}</span>
              </div>
              <div className="col center">
                <span className="section-title">تجربه</span>
                <span>{profile.xp}</span>
              </div>
              <div className="col center">
                <span className="section-title">سطح</span>
                <span>{profile.level}</span>
              </div>
            </div>
          )}
        </div>
      )}
      {error && <div className="status error mt">{error}</div>}
      <div className="col mt center" style={{ gap: 12, width: "100%" }}>
        <button className="btn primary block" onClick={() => navigate("game", { gameId })}>
          شروع مجدد
        </button>
        <button className="btn block" onClick={() => navigate("home")}>
          خانه
        </button>
      </div>
    </div>
  );
}
