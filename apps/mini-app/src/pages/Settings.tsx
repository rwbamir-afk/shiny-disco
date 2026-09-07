import { useEffect, useState } from "react";
import type { Navigate } from "../App";
import { api } from "../lib/api";
import { useSession } from "../state/session";

type SettingsData = {
  show_online: boolean; allow_friend_requests: boolean; public_profile: boolean;
  notify_friend_requests: boolean; notify_friend_accepts: boolean; notify_rewards: boolean;
  sound_enabled: boolean; vibration_enabled: boolean; compact_cards: boolean; auto_sort_hand: boolean;
  preferred_card_speed: "slow" | "normal" | "fast"; theme: string; language: "fa" | "en";
};
const defaults: SettingsData = { show_online:true, allow_friend_requests:true, public_profile:true, notify_friend_requests:true, notify_friend_accepts:true, notify_rewards:true, sound_enabled:true, vibration_enabled:true, compact_cards:false, auto_sort_hand:true, preferred_card_speed:"normal", theme:"iranian", language:"fa" };
export function Settings({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession(); const [data,setData]=useState(defaults); const [saved,setSaved]=useState(false); const [error,setError]=useState<string|null>(null);
  useEffect(()=>{ api<SettingsData>("/api/v1/users/me/settings",{token:accessToken}).then(setData).catch(e=>setError(e instanceof Error?e.message:"خطا")); },[accessToken]);
  async function save(patch: Partial<SettingsData>) { setData(v=>({...v,...patch})); setSaved(false); try { await api("/api/v1/users/me/settings",{method:"PATCH",token:accessToken,body:patch}); setSaved(true); } catch(e){setError(e instanceof Error?e.message:"ذخیره نشد");} }
  return <div className="app pad col"><h2>تنظیمات</h2>{error&&<div className="status error">{error}</div>}{saved&&<div className="status good">تنظیمات ذخیره شد ✓</div>}
    <section className="panel pad col"><div className="section-title">حریم خصوصی</div><Toggle label="نمایش آنلاین بودن" value={data.show_online} onChange={v=>save({show_online:v})}/><Toggle label="پروفایل عمومی" value={data.public_profile} onChange={v=>save({public_profile:v})}/><Toggle label="دریافت درخواست دوستی" value={data.allow_friend_requests} onChange={v=>save({allow_friend_requests:v})}/></section>
    <section className="panel pad col mt"><div className="section-title">اعلان‌ها</div><Toggle label="درخواست دوستی" value={data.notify_friend_requests} onChange={v=>save({notify_friend_requests:v})}/><Toggle label="قبول شدن دوستی" value={data.notify_friend_accepts} onChange={v=>save({notify_friend_accepts:v})}/><Toggle label="پاداش‌ها" value={data.notify_rewards} onChange={v=>save({notify_rewards:v})}/></section>
    <section className="panel pad col mt"><div className="section-title">تجربه بازی</div><Toggle label="صدا" value={data.sound_enabled} onChange={v=>save({sound_enabled:v})}/><Toggle label="لرزش" value={data.vibration_enabled} onChange={v=>save({vibration_enabled:v})}/><Toggle label="مرتب‌سازی خودکار دست" value={data.auto_sort_hand} onChange={v=>save({auto_sort_hand:v})}/><Toggle label="کارت‌های فشرده" value={data.compact_cards} onChange={v=>save({compact_cards:v})}/><label className="row" style={{justifyContent:"space-between"}}>سرعت کارت<select value={data.preferred_card_speed} onChange={e=>save({preferred_card_speed:e.target.value as SettingsData["preferred_card_speed"]})}><option value="slow">آرام</option><option value="normal">عادی</option><option value="fast">سریع</option></select></label></section>
    <button className="btn ghost mt" onClick={()=>navigate("profile")}>بازگشت به پروفایل</button></div>;
}
function Toggle({label,value,onChange}:{label:string;value:boolean;onChange:(v:boolean)=>void}){return <button className="row" style={{justifyContent:"space-between",minHeight:48,background:"transparent",border:0,color:"inherit",textAlign:"right"}} onClick={()=>onChange(!value)}><span>{label}</span><strong>{value?"روشن":"خاموش"}</strong></button>}
