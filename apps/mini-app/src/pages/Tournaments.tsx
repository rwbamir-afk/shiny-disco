import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Navigate } from "../App";

type Tournament = { id:string; name:string; bracket_size:number; status:string; entry_fee:number; prize_coins:number };
type Match = { id:string; round:number; slot:number; player_a_id:string|null; player_b_id:string|null; player_c_id:string|null; player_d_id:string|null; winner_id:string|null; game_id:string|null; status:string };
export function Tournaments({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession(); const [items,setItems]=useState<Tournament[]>([]); const [matches,setMatches]=useState<Record<string,Match[]>>({}); const [error,setError]=useState("");
  async function load(){try{setItems((await api<{tournaments:Tournament[]}>("/api/v1/tournaments",{token:accessToken})).tournaments)}catch(e){setError(e instanceof Error?e.message:"خطا")}}
  useEffect(()=>{void load()},[]);
  async function join(id:string){try{await api(`/api/v1/tournaments/${id}/join`,{method:"POST",token:accessToken});await load()}catch(e){setError(e instanceof Error?e.message:"خطا")}}
  async function open(id:string){try{const r=await api<any>(`/api/v1/tournaments/${id}`,{token:accessToken});setMatches(x=>({...x,[id]:r.matches||[]}))}catch(e){setError(e instanceof Error?e.message:"خطا")}}
  async function startMatch(tid:string,mid:string){try{const r=await api<any>(`/api/v1/tournaments/${tid}/matches/${mid}/start`,{method:"POST",token:accessToken});if(r.game_id) window.location.hash=`#/game/${r.game_id}`; }catch(e){setError(e instanceof Error?e.message:"خطا")}}
  return <div className="app pad col"><button className="btn ghost" onClick={()=>navigate("home")}>← بازگشت</button><h1 className="display">🏆 تورنمنت‌ها</h1>{error&&<div className="status error mt">{error}</div>}<div className="col mt" style={{gap:10}}>{items.map(t=><div className="panel" key={t.id}><b>{t.name}</b><div className="muted">{t.bracket_size} نفره · {t.status==="registration"?"ثبت‌نام باز":"در حال برگزاری"}</div><div className="muted">ورودی: {t.entry_fee.toLocaleString()} 🪙 · جایزه: {t.prize_coins.toLocaleString()} 🪙</div>{t.status==="registration"&&<button className="btn primary mt" onClick={()=>void join(t.id)}>شرکت در تورنمنت</button>}<button className="btn ghost mt" onClick={()=>void open(t.id)}>نمایش براکت</button>{(matches[t.id]||[]).map(m=><div className="panel mt" key={m.id}><b>راند {m.round} · بازی {m.slot+1}</b><div className="muted">{m.status==="finished"?"تمام شده":m.status==="playing"?"در حال بازی":"آماده شروع"}</div>{m.status==="ready"&&<button className="btn primary mt" onClick={()=>void startMatch(t.id,m.id)}>شروع بازی</button>}{m.game_id&&<div className="muted mt">Game: {m.game_id}</div>}</div>)}</div>)}</div></div>;
}
