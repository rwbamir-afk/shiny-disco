import type { PlayerMeta } from "../lib/contracts";

const SEAT_LABEL: Record<number, string> = { 0: "شمال", 1: "راست", 2: "جنوب", 3: "چپ" };

export function PlayerSeat({
  meta,
  current,
  cardsInHand,
  team,
  isHakem,
}: {
  meta: PlayerMeta;
  current: boolean;
  cardsInHand: number;
  team: string;
  isHakem?: boolean;
}) {
  return (
    <div className={`playerpill ${current ? "current" : ""} ${team === "A" ? "partner" : ""}`}>
      <span className="name">
        {isHakem && <span className="hakem-star">★ </span>}
        {meta.is_bot ? `🖥 ${meta.display_name}` : meta.display_name}
      </span>
      <span className="count">{cardsInHand} کارت</span>
      <span className="count">{SEAT_LABEL[meta.seat] ?? meta.seat}</span>
    </div>
  );
}
