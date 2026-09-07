import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Navigate } from "../App";

type Person = { id: string; username?: string | null; display_name: string; avatar_url?: string | null; online?: boolean; last_seen?: string | null };
type Request = { id: string; user: Person };
type Notice = { id: string; title: string; body: string; read: boolean };

export function Social({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession();
  const [friends, setFriends] = useState<Person[]>([]);
  const [requests, setRequests] = useState<Request[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [results, setResults] = useState<Person[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [f, r, n] = await Promise.all([
        api<{ friends: Person[] }>("/api/v1/social/friends", { token: accessToken }),
        api<{ requests: Request[] }>("/api/v1/social/requests", { token: accessToken }),
        api<{ notifications: Notice[] }>("/api/v1/social/notifications", { token: accessToken }),
      ]);
      setFriends(f.friends); setRequests(r.requests); setNotices(n.notifications);
    } catch (e) { setError(e instanceof Error ? e.message : "خطا"); }
  }
  useEffect(() => { void load(); }, [accessToken]);

  async function search() {
    if (query.trim().length < 2) return setResults([]);
    try { setResults((await api<{ users: Person[] }>(`/api/v1/social/search?q=${encodeURIComponent(query)}`, { token: accessToken })).users); }
    catch (e) { setError(e instanceof Error ? e.message : "خطا"); }
  }
  async function send(id: string) { await api(`/api/v1/social/requests/${id}`, { method: "POST", token: accessToken }); await load(); await search(); }
  async function accept(id: string) { await api(`/api/v1/social/requests/${id}/accept`, { method: "POST", token: accessToken }); await load(); }
  async function reject(id: string) { await api(`/api/v1/social/requests/${id}/reject`, { method: "POST", token: accessToken }); await load(); }
  async function remove(id: string) { await api(`/api/v1/social/friends/${id}`, { method: "DELETE", token: accessToken }); await load(); }
  async function markRead() { await api("/api/v1/social/notifications/read-all", { method: "POST", token: accessToken }); await load(); }

  return <div className="app pad col">
    <div className="row"><div className="grow"><h2>دوستان و اجتماع</h2><div className="section-title">بازیکن پیدا کن، درخواست بده و ارتباطاتت را مدیریت کن</div></div><button className="btn icon" onClick={() => navigate("home")}>×</button></div>
    <div className="panel pad col">
      <div className="row"><input className="social-input" value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === "Enter" && void search()} placeholder="نام کاربری یا نام بازیکن"/><button className="btn secondary" onClick={() => void search()}>جستجو</button></div>
      {results.map(p => <div className="social-person" key={p.id}><span className="grow">{p.display_name}{p.username ? ` @${p.username}` : ""} {p.online ? "🟢" : "⚪"}</span><button className="btn icon" onClick={() => void send(p.id)}>＋</button></div>)}
    </div>
    {requests.length > 0 && <section className="panel pad col"><h3>درخواست‌ها</h3>{requests.map(r => <div className="social-person" key={r.id}><span className="grow">{r.user.display_name}</span><button className="btn icon" onClick={() => void accept(r.id)}>✓</button><button className="btn icon" onClick={() => void reject(r.id)}>×</button></div>)}</section>}
    <section className="panel pad col"><div className="row"><h3 className="grow">دوستان ({friends.length})</h3></div>{friends.length ? friends.map(p => <div className="social-person" key={p.id}><span className="grow">{p.display_name} <small>{p.online ? "🟢 آنلاین" : "⚪ آفلاین"}</small></span><button className="btn ghost" onClick={() => void remove(p.id)}>حذف</button></div>) : <div className="status info">هنوز دوستی اضافه نکرده‌ای.</div>}</section>
    <section className="panel pad col"><div className="row"><h3 className="grow">اعلان‌ها</h3>{notices.some(n => !n.read) && <button className="btn ghost" onClick={() => void markRead()}>خواندم</button>}</div>{notices.slice(0, 8).map(n => <div className="notice" key={n.id} onClick={() => void (n.read ? Promise.resolve() : api(`/api/v1/social/notifications/${n.id}/read`, { method: "POST", token: accessToken }).then(load))}><b>{n.title}</b><div>{n.body}</div>{!n.read && <small>برای خواندن لمس کن</small>}</div>)}{!notices.length && <div className="status info">اعلان جدیدی نداری.</div>}</section>
    {error && <div className="status error">{error}</div>}
    <button className="btn ghost" onClick={() => navigate("home")}>بازگشت</button>
  </div>;
}
