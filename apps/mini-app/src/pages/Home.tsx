import { useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Navigate } from "../App";

export function Home({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession();
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function quickMatch() {
    setError(null);
    setSearching(true);
    try {
      await api("/api/v1/matchmaking/quick", { method: "POST", body: { mode: "quick" }, token: accessToken });
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        const st = await api<{ status: string; game_id?: string }>("/api/v1/matchmaking/status", { token: accessToken });
        if (st.status === "matched" && st.game_id) {
          navigate("game", { gameId: st.game_id });
          return;
        }
      }
      setError("بازی پیدا نشد؛ کمی بعد دوباره تلاش کنید.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="app pad col">
      <h1 className="display">حکم</h1>
      <p className="section-title">بازی تیمی چهار نفره</p>
      <div className="col mt" style={{ gap: 12 }}>
        <button className="btn primary block" onClick={quickMatch} disabled={searching}>
          {searching ? "در حال پیدا کردن بازیکن…" : "بازی سریع"}
        </button>
        <button className="btn block" onClick={() => navigate("room")}>
          بازی با دوستان
        </button>
        <button className="btn ghost block" onClick={() => navigate("profile")}>
          پروفایل من
        </button>
        <button className="btn ghost block" onClick={() => navigate("ranking")}>
          رتبه‌بندی
        </button>
        <button className="btn ghost block" onClick={() => navigate("economy")}>
          🪙 بازار و کمد
        </button>
        <button className="btn ghost block" onClick={() => navigate("progression")}>
          🏆 مأموریت و دستاورد
        </button>
        <button className="btn ghost block" onClick={() => navigate("social")}>
          👥 دوستان و اعلان‌ها
        </button>
        <button className="btn ghost block" onClick={() => navigate("clubs")}>
          🛡️ باشگاه‌ها
        </button>
        <button className="btn ghost block" onClick={() => navigate("tournaments")}>
          🏆 تورنمنت‌ها
        </button>
        <button className="btn ghost block" onClick={() => navigate("premium")}>
          💎 Battle Pass و VIP
        </button>
      </div>
      {error && <div className="status error mt">{error}</div>}
    </div>
  );
}
