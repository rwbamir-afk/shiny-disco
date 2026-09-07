import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Navigate } from "../App";

type Item = { id: string; name: string; category: string; description: string; price_coins: number; rarity: string; asset_key: string };
type InventoryItem = Item & { inventory_id: string; equipped: boolean };

export function Economy({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession();
  const [coins, setCoins] = useState(0);
  const [items, setItems] = useState<Item[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [message, setMessage] = useState("");
  const [daily, setDaily] = useState<{ claimed: boolean; reward_coins: number; streak_day: number } | null>(null);

  async function load() {
    const [w, s, inv] = await Promise.all([
      api<{ coins: number }>("/api/v1/economy/wallet", { token: accessToken }),
      api<{ items: Item[] }>("/api/v1/economy/shop", { token: accessToken }),
      api<{ items: InventoryItem[] }>("/api/v1/economy/inventory", { token: accessToken }),
    ]);
    setCoins(w.coins); setItems(s.items); setInventory(inv.items);
  }
  useEffect(() => { void load(); }, [accessToken]);

  async function claim() {
    try { const d = await api<typeof daily>("/api/v1/economy/daily", { method: "POST", token: accessToken }); setDaily(d); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "خطا"); }
  }
  async function buy(id: string) {
    try { await api(`/api/v1/economy/shop/${id}/buy`, { method: "POST", token: accessToken }); setMessage("آیتم به کمدت اضافه شد."); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "خرید ناموفق بود"); }
  }
  async function equip(id: string) {
    try { await api(`/api/v1/economy/inventory/${id}/equip`, { method: "POST", token: accessToken }); await load(); }
    catch (e) { setMessage(e instanceof Error ? e.message : "خطا"); }
  }

  return <div className="app pad col">
    <div className="row"><button className="btn ghost" onClick={() => navigate("home")}>←</button><h2 className="grow">بازار و کمد</h2><strong>🪙 {coins}</strong></div>
    <div className="panel pad col mt"><div className="row"><div><div className="section-title">پاداش روزانه</div><div>هر روز وارد شو و جایزه بگیر.</div></div><button className="btn primary" onClick={claim}>دریافت</button></div>{daily && <div className="status info mt">{daily.claimed ? `روز ${daily.streak_day}: +${daily.reward_coins} سکه` : "امروز قبلاً دریافت شده"}</div>}</div>
    <h3 className="mt">فروشگاه</h3>
    <div className="col">{items.map(x => <div className="panel pad" key={x.id}><div className="row"><div className="grow"><strong>{x.name}</strong><div className="section-title">{x.rarity} · {x.description}</div></div><button className="btn secondary" onClick={() => buy(x.id)}>🪙 {x.price_coins}</button></div></div>)}</div>
    <h3 className="mt">کمد من</h3>
    {inventory.length === 0 ? <div className="status info">هنوز آیتمی نداری.</div> : inventory.map(x => <div className="panel pad" key={x.inventory_id}><div className="row"><span className="grow">{x.name}</span>{x.equipped ? <span>مجهز ✓</span> : <button className="btn" onClick={() => equip(x.id)}>استفاده</button>}</div></div>)}
    {message && <div className="status info mt">{message}</div>}
  </div>;
}
