import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Navigate } from "../App";

type BP = { season: { title: string; ends_at: string; max_level: number; premium_price_gems: number }; pass: { xp: number; level: number; premium: boolean; claimed_free: number[]; claimed_premium: number[] }; rewards: { level: number; free_coins: number; premium_gems: number }[] };
type Product = { product: string; stars: number; gems?: number; duration_days?: number };

export function Premium({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession();
  const [gems, setGems] = useState(0);
  const [bp, setBp] = useState<BP | null>(null);
  const [vip, setVip] = useState<{ active: boolean; tier: string | null; ends_at: string | null }>({ active: false, tier: null, ends_at: null });
  const [products, setProducts] = useState<Product[]>([]);
  const [message, setMessage] = useState("");

  async function load() {
    const [w, b, v, c] = await Promise.all([
      api<{ gems: number }>("/api/v1/premium/wallet", { token: accessToken }),
      api<BP>("/api/v1/premium/battle-pass", { token: accessToken }),
      api<typeof vip>("/api/v1/premium/vip", { token: accessToken }),
      api<{ products: Product[] }>("/api/v1/premium/stars/catalog"),
    ]);
    setGems(w.gems); setBp(b); setVip(v); setProducts(c.products);
  }
  useEffect(() => { void load(); }, [accessToken]);

  async function unlock() {
    try { await api("/api/v1/premium/battle-pass/unlock", { method: "POST", token: accessToken }); setMessage("پَس پریمیوم فعال شد."); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "فعال‌سازی ناموفق بود"); }
  }
  async function claim(level: number, premium: boolean) {
    try { await api("/api/v1/premium/battle-pass/claim", { method: "POST", token: accessToken, body: { level, premium } }); setMessage("پاداش دریافت شد."); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "دریافت پاداش ناموفق بود"); }
  }
  async function intent(product: string) {
    try {
      const x = await api<{ stars: number; payload: string }>("/api/v1/premium/stars/intent", { method: "POST", token: accessToken, body: { product } });
      setMessage(`سفارش ${x.stars} ⭐ ساخته شد. پرداخت واقعی باید از طریق Bot API تلگرام تکمیل شود.`);
    } catch (e) { setMessage(e instanceof Error ? e.message : "خطا"); }
  }

  return <div className="app pad col">
    <div className="row"><button className="btn ghost" onClick={() => navigate("home")}>←</button><h2 className="grow">💎 اقتصاد پریمیوم</h2><strong>💎 {gems}</strong></div>
    {bp && <div className="panel pad col mt">
      <div className="row"><div className="grow"><strong>{bp.season.title}</strong><div className="section-title">تا {new Date(bp.season.ends_at).toLocaleDateString("fa-IR")}</div></div><span>سطح {bp.pass.level}/{bp.season.max_level}</span></div>
      <div className="status info mt">XP فصل: {bp.pass.xp} · {bp.pass.premium ? "پریمیوم فعال ✓" : `پریمیوم: ${bp.season.premium_price_gems} 💎`}</div>
      {!bp.pass.premium && <button className="btn primary mt" onClick={unlock}>فعال‌سازی Battle Pass</button>}
      <div className="col mt">{bp.rewards.filter(r => r.level <= bp.pass.level).map(r => <div className="row panel" key={r.level} style={{padding: 10}}><span>سطح {r.level}</span><span className="grow">🪙 {r.free_coins} · 💎 {r.premium_gems}</span>{r.level <= bp.pass.level && !bp.pass.claimed_free.includes(r.level) && <button className="btn secondary" onClick={() => claim(r.level, false)}>دریافت رایگان</button>}{bp.pass.premium && !bp.pass.claimed_premium.includes(r.level) && <button className="btn" onClick={() => claim(r.level, true)}>پریمیوم</button>}</div>)}</div>
    </div>}
    <div className="panel pad col mt"><strong>خرید با Telegram Stars</strong><div className="section-title">این مرحله فقط سفارش امن ایجاد می‌کند؛ تأیید پرداخت باید از سرویس پرداخت Bot انجام شود.</div>{products.map(p => <div className="row" key={p.product}><span className="grow">{p.gems ? `${p.gems} 💎` : "VIP · ۳۰ روز"}</span><button className="btn secondary" onClick={() => intent(p.product)}>⭐ {p.stars}</button></div>)}</div>
    {vip.active && <div className="status good mt">VIP فعال است تا {new Date(vip.ends_at!).toLocaleDateString("fa-IR")}</div>}
    {message && <div className="status info mt">{message}</div>}
  </div>;
}
