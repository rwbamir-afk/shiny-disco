import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Navigate } from "../App";

type Club = { id: string; name: string; tag: string; description: string; privacy: string; members: number; max_members: number; level: number; xp: number };

export function Clubs({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession();
  const [clubs, setClubs] = useState<Club[]>([]); const [q, setQ] = useState(""); const [error, setError] = useState("");
  async function load() { try { const x = await api<{clubs: Club[]}>(`/api/v1/clubs?q=${encodeURIComponent(q)}`, { token: accessToken }); setClubs(x.clubs); } catch (e) { setError(e instanceof Error ? e.message : "خطا"); } }
  useEffect(() => { void load(); }, []);
  async function join(c: Club) { setError(""); try { await api(`/api/v1/clubs/${c.id}/join`, { method: "POST", token: accessToken }); await load(); } catch (e) { setError(e instanceof Error ? e.message : "خطا"); } }
  return <div className="app pad col"><button className="btn ghost" onClick={() => navigate("home")}>← بازگشت</button><h1 className="display">باشگاه‌ها</h1><div className="row"><input className="input" value={q} onChange={e=>setQ(e.target.value)} placeholder="نام یا تگ باشگاه"/><button className="btn" onClick={()=>void load()}>جستجو</button></div>{error && <div className="status error mt">{error}</div>}<div className="col mt" style={{gap:10}}>{clubs.map(c=><div className="panel" key={c.id}><b>{c.name} <span className="muted">[{c.tag}]</span></b><div className="muted">{c.description || "باشگاه حکم"}</div><div className="muted">👥 {c.members}/{c.max_members} · سطح {c.level}</div><button className="btn primary mt" onClick={()=>void join(c)}>عضویت</button></div>)}</div></div>;
}
