import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Profile } from "../lib/contracts";
import type { Navigate } from "../App";

export function Profile({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<import("../lib/contracts").GameHistoryEntry[]>([]);

  useEffect(() => {
    api<{ profile: Profile }>("/api/v1/users/me", { token: accessToken })
      .then((d) => setProfile(d.profile))
      .catch((e) => setError(e instanceof Error ? e.message : "خطا"));
  }, [accessToken]);

  useEffect(() => {
    api<{ games: import("../lib/contracts").GameHistoryEntry[] }>("/api/v1/games/history/mine?limit=10", { token: accessToken })
      .then((d) => setHistory(d.games))
      .catch(() => undefined);
  }, [accessToken]);

  return (
    <div className="app pad col">
      <h2>پروفایل</h2>
      {profile ? (
        <div className="panel pad col">
          <div className="row">
            <div className="grow">
              <div className="section-title">نام</div>
              <div className="display" style={{ fontSize: 22 }}>
                {profile.display_name}
              </div>
            </div>
            <div className="col center">
              <span className="section-title">سطح</span>
              <span className="display">{profile.level}</span>
            </div>
          </div>
          <hr className="divider" />
          <div className="row" style={{ justifyContent: "space-around" }}>
            <Stat label="امتیاز" value={String(profile.rating)} />
            <Stat label="رتبه" value={profile.rank_tier?.title ?? "—"} />
            <Stat label="سهم برد" value={`${profile.win_rate}%`} />
            <Stat label="بازی‌ها" value={String(profile.games_played)} />
            <Stat label="برد" value={String(profile.wins)} />
          </div>
          <hr className="divider" />
          <div className="section-title">
            تجربه: {profile.xp} — رکورد برد متوالی: {profile.max_streak}
          </div>
        </div>
      ) : (
        <div className="status info">در حال بارگذاری…</div>
      )}
      <div className="panel pad col mt">
        <div className="section-title">آخرین بازی‌ها</div>
        {history.map((g) => (
          <div className="row" key={g.game_id}>
            <span className="grow">{g.won ? "برد" : "باخت"} · {g.scores.A}-{g.scores.B}</span>
            <span>{g.rating_change > 0 ? "+" : ""}{g.rating_change}</span>
            <span>{g.coins_gained} 🪙</span>
          </div>
        ))}
        {!history.length && <span className="section-title">هنوز بازی تمام‌شده‌ای ثبت نشده</span>}
      </div>
      {error && <div className="status error mt">{error}</div>}
      <button className="btn secondary mt" onClick={() => navigate("settings")}>تنظیمات</button>
      <button className="btn ghost mt" onClick={() => navigate("home")}>
        بازگشت
      </button>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="col center">
      <span className="section-title">{label}</span>
      <span style={{ fontWeight: 800 }}>{value}</span>
    </div>
  );
}
