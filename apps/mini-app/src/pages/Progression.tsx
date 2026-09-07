import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Navigate } from "../App";

type Mission = { id: string; title: string; description: string; progress: number; target: number; reward_coins: number; reward_xp: number; claimable: boolean; claimed: boolean };
type Achievement = { id: string; title: string; description: string; target: number; reward_coins: number; reward_xp: number; unlocked: boolean };
type Progress = { level: number; xp: number; missions: Mission[]; achievements: Achievement[] };

export function Progression({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession(); const [p, setP] = useState<Progress | null>(null); const [msg, setMsg] = useState("");
  async function load() { setP(await api<Progress>("/api/v1/progression", { token: accessToken })); }
  useEffect(() => { void load(); }, [accessToken]);
  async function claim(id: string) { try { await api(`/api/v1/progression/missions/${id}/claim`, { method: "POST", token: accessToken }); setMsg("پاداش مأموریت دریافت شد."); await load(); } catch (e) { setMsg(e instanceof Error ? e.message : "خطا"); } }
  if (!p) return <div className="app pad"><div className="status info">در حال بارگذاری…</div></div>;
  return <div className="app pad col"><div className="row"><button className="btn ghost" onClick={() => navigate("home")}>←</button><h2 className="grow">پیشرفت</h2><strong>سطح {p.level}</strong></div><div className="panel pad mt"><div className="section-title">XP</div><strong>{p.xp.toLocaleString("fa-IR")}</strong></div><h3 className="mt">مأموریت‌ها</h3>{p.missions.map(m => <div className="panel pad" key={m.id}><div className="row"><div className="grow"><strong>{m.title}</strong><div>{m.description}</div><div className="section-title">{m.progress} / {m.target} · 🪙 {m.reward_coins} · XP {m.reward_xp}</div></div>{m.claimable ? <button className="btn primary" onClick={() => claim(m.id)}>دریافت</button> : <span>{m.claimed ? "✓" : "در جریان"}</span>}</div></div>)}<h3 className="mt">دستاوردها</h3>{p.achievements.map(a => <div className="panel pad" key={a.id}><strong>{a.unlocked ? "🏆 " : "🔒 "}{a.title}</strong><div>{a.description}</div><div className="section-title">هدف {a.target} · 🪙 {a.reward_coins} · XP {a.reward_xp}</div></div>)}{msg && <div className="status info mt">{msg}</div>}</div>;
}
