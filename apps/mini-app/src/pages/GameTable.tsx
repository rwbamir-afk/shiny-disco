import { useEffect, useRef, useState } from "react";
import { GameSocket } from "../lib/ws";
import { useSession } from "../state/session";
import type { PlayerGameView } from "../lib/contracts";
import { PlayingCard, trumpName } from "../components/Card";
import { PlayerSeat } from "../components/PlayerSeat";
import { playUiSound } from "../lib/sound";
import type { Navigate } from "../App";

const SUITS = ["hearts", "diamonds", "clubs", "spades"];
const SUIT_FA: Record<string, string> = { hearts: "دل", diamonds: "خشت", clubs: "گشاد", spades: "خاج" };
const SUIT_SYMBOL: Record<string, string> = { hearts: "♥", diamonds: "♦", clubs: "♣", spades: "♠" };

function rnd() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function GameTable({ gameId, navigate }: { gameId: string; navigate: Navigate }) {
  const { accessToken } = useSession();
  const [view, setView] = useState<PlayerGameView | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sockRef = useRef<GameSocket | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    const sock = new GameSocket(accessToken);
    sockRef.current = sock;
    sock.onMessage((msg) => {
      if (msg.type === "game.state") {
        setView(msg.data);
        if (msg.data.phase === "game_ended") {
          sock.close();
          navigate("result", { gameId, team: msg.data.team });
        }
      } else if (msg.type === "error") {
        setError(msg.error);
      }
    });
    sock.connect();
    sock.subscribe(gameId);
    return () => sock.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, accessToken]);

  function playCard(card: string) {
    if (!view || !view.is_my_turn) return;
    if (!view.legal_cards.includes(card)) return;
    sockRef.current?.sendAction(gameId, { type: "play_card", card, request_id: rnd() });
    playUiSound("card");
    setSelected(null);
  }

  function selectTrump(trump: string) {
    sockRef.current?.sendAction(gameId, { type: "select_trump", trump, request_id: rnd() });
    playUiSound("trump");
  }

  const secondsLeft = view?.turn_deadline ? Math.max(0, Math.floor((view.turn_deadline - Date.now()) / 1000)) : null;
  const showTrumpPicker = view?.phase === "trump_selection" && view.seat === view.hakem_seat;

  return (
    <div className="app game-screen">
      <div className="scorebar">
        <span className="teamchip team-A">
          <span className="teamdot" /> تیم شما ({view?.scores.A ?? 0})
        </span>
        <span className="teamchip team-B">
          <span className="teamdot" /> حریف ({view?.scores.B ?? 0})
        </span>
      </div>

      <div className="trumpbar">
        <span className="section-title">حکم</span>
        <span className="badge">{view ? trumpName(view.trump) : "—"}</span>
        <span className="grow" />
        {view?.phase === "trump_selection" && (
          <span className="badge" style={{ background: "var(--paper-2)" }}>
            انتخاب حکم توسط حاکم
          </span>
        )}
      </div>

      {/* Opponents / partner */}
      <div className="seatrow">
        {(view?.players ?? []).slice(0, 2).map((p) => (
          <PlayerSeat
            key={p.seat}
            meta={p}
            current={view?.current_player === p.seat}
            cardsInHand={view?.table.find((t) => t.seat === p.seat)?.cards_in_hand ?? 0}
            team={p.seat % 2 === 0 ? "A" : "B"}
            isHakem={view?.hakem_seat === p.seat}
          />
        ))}
      </div>

      {/* Current trick */}
      <div className="table-3d-wrap"><div className="trickzone panel table-3d">
        {(view?.trick.plays ?? []).map(([seat, card]) => (
          <PlayingCard key={`${seat}-${card}`} id={card} played size="sm" />
        ))}
        {!view?.trick.plays.length && <span className="section-title">دست جاری</span>}
      </div></div>

      <div className="seatrow">
        {(view?.players ?? []).slice(2).map((p) => (
          <PlayerSeat
            key={p.seat}
            meta={p}
            current={view?.current_player === p.seat}
            cardsInHand={view?.table.find((t) => t.seat === p.seat)?.cards_in_hand ?? 0}
            team={p.seat % 2 === 0 ? "A" : "B"}
            isHakem={view?.hakem_seat === p.seat}
          />
        ))}
      </div>

      {showTrumpPicker && (
        <div className="suittabs">
          {SUITS.map((s) => (
            <button key={s} className="suittab" onClick={() => selectTrump(s)} aria-label={SUIT_FA[s]}>
              {SUIT_SYMBOL[s]}
            </button>
          ))}
        </div>
      )}

      {!showTrumpPicker && (
        <div className="tablerow">
          <div className="row pad" style={{ justifyContent: "center", minHeight: 36 }}>
            {view?.is_my_turn && !secondsLeft ? (
              <span className="section-title">نوبت شماست</span>
            ) : (
              <span className={`timer ${secondsLeft !== null && secondsLeft <= 5 ? "low" : ""}`}>
                {secondsLeft !== null ? `${secondsLeft}s` : "—"}
              </span>
            )}
          </div>
          <div className="hand">
            {(view?.hand ?? []).map((card) => (
              <PlayingCard
                key={card}
                id={card}
                selected={selected === card}
                illegal={!view?.legal_cards.includes(card)}
                onClick={() => {
                  if (view?.is_my_turn && view.legal_cards.includes(card)) {
                    setSelected((p) => (p === card ? null : card));
                    playCard(card);
                  }
                }}
              />
            ))}
          </div>
        </div>
      )}

      {error && <div className="status error mt">{error}</div>}
      {view?.phase === "game_ended" && !error && <div className="status info mt">بازی تمام شد</div>}
    </div>
  );
}
