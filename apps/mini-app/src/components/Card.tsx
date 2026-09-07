import type { CSSProperties } from "react";

const SUIT_SYMBOL: Record<string, string> = {
  s: "\u2660",
  h: "\u2665",
  d: "\u2666",
  c: "\u2663",
};
const SUIT_NAME: Record<string, string> = {
  s: "خاج",
  h: "دل",
  d: "خشت",
  c: "گشاد",
};
const RED_SUITS = new Set(["h", "d"]);
const RANK_LABEL: Record<string, string> = {
  "2": "۲", "3": "۳", "4": "۴", "5": "۵", "6": "۶", "7": "۷", "8": "۸", "9": "۹",
  "10": "۱۰", J: "سرباز", Q: "بانو", K: "شاه", A: "آس",
};

export function cardParts(id: string) {
  const suit = id[0];
  const rank = id.slice(1);
  return {
    suit,
    rank,
    rankFa: RANK_LABEL[rank] ?? rank,
    symbol: SUIT_SYMBOL[suit] ?? "",
    name: SUIT_NAME[suit] ?? "",
    red: RED_SUITS.has(suit),
  };
}

export function trumpName(suit: string | null): string {
  return suit ? `${SUIT_NAME[suit] ?? ""} (${SUIT_SYMBOL[suit] ?? ""})` : "—";
}

export function PlayingCard({
  id,
  selected = false,
  illegal = false,
  played = false,
  onClick,
  size,
}: {
  id: string;
  selected?: boolean;
  illegal?: boolean;
  played?: boolean;
  onClick?: () => void;
  size?: "sm" | "md";
}) {
  const c = cardParts(id);
  const style: CSSProperties = size === "sm" ? { width: 46, height: 68 } : {};
  return (
    <button
      type="button"
      className={[
        "pcard",
        c.red ? "red" : "black",
        selected ? "selected" : "",
        illegal ? "illegal" : "",
        played ? "played" : "",
      ].join(" ")}
      style={style}
      onClick={onClick}
      disabled={played || illegal}
      aria-label={`${c.rankFa} ${c.name}`}
    >
      <span className="card-corner card-corner-top"><span className="rank">{c.rankFa}</span><span className="suit">{c.symbol}</span></span>
      <span className="card-medallion" aria-hidden="true">{c.symbol}</span>
      <span className="card-corner card-corner-bottom" aria-hidden="true"><span className="rank">{c.rankFa}</span><span className="suit">{c.symbol}</span></span>
    </button>
  );
}
