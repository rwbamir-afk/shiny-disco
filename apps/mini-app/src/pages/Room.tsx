import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { useSession } from "../state/session";
import type { Room, RoomPlayer } from "../lib/contracts";
import type { Navigate } from "../App";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback for older WebViews without Clipboard API support.
      const el = document.createElement("textarea");
      el.value = text;
      el.style.position = "fixed";
      el.style.opacity = "0";
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button className={`copy-btn ${copied ? "copied" : ""}`} onClick={copy}>
      {copied ? "کپی شد ✓" : "کپی"}
    </button>
  );
}

export function Room({ navigate }: { navigate: Navigate }) {
  const { accessToken } = useSession();
  const [room, setRoom] = useState<Room | null>(null);
  const [inviteInput, setInviteInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  const loadRoom = useCallback(
    async (id: string) => {
      const r = await api<Room>(`/api/v1/rooms/${id}`, { token: accessToken });
      setRoom(r);
      return r;
    },
    [accessToken]
  );

  async function createRoom() {
    setError(null);
    try {
      const r = await api<Room>("/api/v1/rooms", { method: "POST", body: {}, token: accessToken });
      setRoom(r);
      poll(r.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا");
    }
  }

  async function joinRoom() {
    setError(null);
    try {
      const r = await api<Room>("/api/v1/rooms/join", {
        method: "POST",
        body: { invite_code: inviteInput.trim() },
        token: accessToken,
      });
      setRoom(r);
      poll(r.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "اتاق پیدا نشد");
    }
  }

  async function toggleReady() {
    if (!room) return;
    const me = room.players.find((p) => p.user_id && p.user_id === sessionUserId());
    const next = !(me?.ready ?? false);
    await api(`/api/v1/rooms/${room.id}/ready`, { method: "POST", body: { ready: next }, token: accessToken });
    await loadRoom(room.id);
  }

  function sessionUserId() {
    try {
      return JSON.parse(sessionStorage.getItem("hokm.session") ?? "{}").user?.id as string;
    } catch {
      return "";
    }
  }

  async function startGame() {
    if (!room) return;
    setError(null);
    try {
      await api(`/api/v1/rooms/${room.id}/start`, { method: "POST", body: {}, token: accessToken });
      startedRef.current = true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "شروع نشد؛ همه آماده نیستند؟");
    }
  }

  function poll(id: string) {
    const t = setInterval(async () => {
      try {
        const r = await loadRoom(id);
        if (r.players.length >= 2 && r.players.length === 4) clearInterval(t);
      } catch {
        clearInterval(t);
      }
    }, 2500);
  }

  useEffect(() => {
    if (room?.status === "ingame" && startedRef.current) {
      // The game start endpoint doesn't return the game id on the room; the
      // game is created on the server. We poll the game list via the WS flow.
    }
  }, [room]);

  return (
    <div className="app pad col">
      <h2>بازی با دوستان</h2>
      {!room ? (
        <div className="col">
          <button className="btn primary block" onClick={createRoom}>
            ساخت اتاق
          </button>
          <div className="row mt">
            <input
              value={inviteInput}
              onChange={(e) => setInviteInput(e.target.value)}
              placeholder="کد دعوت"
              inputMode="text"
              style={{ flex: 1, minHeight: 52, padding: "0 14px", borderRadius: 8, border: "2px solid var(--ink)" }}
            />
            <button className="btn" onClick={joinRoom}>
              ورود
            </button>
          </div>
          {error && <div className="status error mt">{error}</div>}
          <button className="btn ghost mt" onClick={() => navigate("home")}>
            بازگشت
          </button>
        </div>
      ) : (
        <div className="col">
          <div className="panel pad">
            <div className="section-title">کد دعوت</div>
            <div className="invite-row mt">
              <span className="invite-code" dir="ltr">{room.invite_code}</span>
              <CopyButton text={room.invite_code} />
            </div>
          </div>
          <div className="col mt">
            {room.players.map((p: RoomPlayer) => (
              <div key={p.user_id ?? p.seat} className="panel pad row">
                <span className="grow">{p.display_name || (p.user_id ? "بازیکن" : "—")}</span>
                <span className="badge">{p.ready ? "آماده" : "در انتظار"}</span>
              </div>
            ))}
            {Array.from({ length: Math.max(0, 4 - room.players.length) }).map((_, i) => (
              <div key={`empty-${i}`} className="panel pad row" style={{ opacity: 0.5 }}>
                <span className="grow">صندلی خالی</span>
              </div>
            ))}
          </div>
          <button className="btn block mt" onClick={toggleReady}>
            تغییر وضعیت آماده
          </button>
          <button className="btn primary block mt" onClick={startGame}>
            شروع بازی
          </button>
          {error && <div className="status error mt">{error}</div>}
          <button className="btn ghost mt" onClick={() => navigate("home")}>
            بازگشت
          </button>
        </div>
      )}
    </div>
  );
}
