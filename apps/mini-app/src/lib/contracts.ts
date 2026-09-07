/**
 * Shared client-safe contracts.
 *
 * IMPORTANT: these mirror ONLY the public surfaces the server exposes
 * (PlayerGameView / UserOut / ProfileOut / RoomOut / ResultOut).
 *
 * The front-end never holds authoritative game state — it only renders
 * server-provided projections.
 *
 * No server-only fields (hands, snapshot, _rng) appear here.
 */

export interface PlayerMeta {
  user_id: string;
  seat: number;
  is_bot: boolean;
  connection_state:
    | "connected"
    | "disconnected"
    | "reconnecting"
    | "bot_controlled"
    | "finished";
  display_name: string;
  username: string | null;
}

export interface PlayerGameView {
  game_id: string;
  rules_version: string;
  phase:
    | "idle"
    | "dealing"
    | "trump_selection"
    | "playing"
    | "game_ended";
  seat: number;
  team: "A" | "B";
  hakem_seat: number;
  trump: string | null;
  current_player: number | null;
  is_my_turn: boolean;
  hand: string[];
  legal_cards: string[];
  trick: {
    leader_seat: number | null;
    plays: [number, string][];
    complete: boolean;
  };
  table: {
    seat: number;
    team: string;
    played: string[];
    cards_in_hand: number;
  }[];
  scores: {
    A: number;
    B: number;
  };
  tricks_played: number;
  winner_team: "A" | "B" | null;
  turn_deadline: number | null;
  timers: Record<string, unknown>;
  players: PlayerMeta[];
  my_meta: PlayerMeta;
}

export interface RoomPlayer {
  user_id: string | null;
  seat: number;
  username: string | null;
  display_name: string;
  is_bot: boolean;
  ready: boolean;
}

export interface Room {
  id: string;
  creator_id: string | null;
  status: string;
  invite_code: string;
  rules_version: string;
  players: RoomPlayer[];
}

export interface Profile {
  user_id: string;
  display_name: string;
  level: number;
  xp: number;
  rating: number;
  rank_tier?: {
    key: string;
    title: string;
    min_rating: number;
  };
  games_played: number;
  wins: number;
  losses: number;
  win_rate: number;
  streak: number;
  max_streak: number;
  bio?: string;
  profile_title?: string;
}

export interface Result {
  game_id: string;
  winner_team: "A" | "B";
  scores: {
    A: number;
    B: number;
  };
  rating_changes: Record<string, number>;
  xp_changes: Record<string, number>;
}

export interface RankingEntry {
  position?: number;
  user_id: string;
  display_name: string;
  rating: number;
  games_played: number;
  wins: number;
  rank_tier?: {
    key: string;
    title: string;
    min_rating: number;
  };
}

export interface GameHistoryEntry {
  game_id: string;
  finished_at: string | null;
  team: "A" | "B";
  won: boolean;
  scores: {
    A: number;
    B: number;
  };
  rating_change: number;
  xp_gained: number;
  coins_gained: number;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export interface Session {
  user: {
    id: string;
    telegram_id: number;
    username: string | null;
    first_name: string;
    last_name: string | null;
    avatar_url: string | null;
  };
  profile: Profile;
  tokens: TokenPair;
}

export type WsMessage =
  | {
      type: "game.state";
      data: PlayerGameView;
    }
  | {
      type: "pong";
      ts?: number;
    }
  | {
      type: "error";
      code: string;
      error: string;
    };
export interface Session {
  user: {
    id: string;
    telegram_id: number;
    username: string | null;
    first_name: string;
    last_name: string | null;
    avatar_url: string | null;
  };
  profile: Profile;
  tokens: TokenPair;
}

export type WsMessage =
  | { type: "game.state"; data: PlayerGameView }
  | { type: "pong"; ts?: number }
  | { type: "error"; code: string; error: string };
