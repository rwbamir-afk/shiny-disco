/**
 * WebSocket client with exponential-backoff reconnect.
 *
 * The server is the source of truth. This client only subscribes and sends
 * typed commands; it never reconstructs authoritative state from cached data.
 */

import type { WsMessage } from "./contracts";

type Handler = (msg: WsMessage) => void;

export class GameSocket {
  private ws: WebSocket | null = null;
  private token: string;
  private handlers = new Set<Handler>();
  private gameId: string | null = null;
  private closed = false;
  private retries = 0;
  private pingTimer: number | null = null;

  constructor(token: string) {
    this.token = token;
  }

  onMessage(fn: Handler): () => void {
    this.handlers.add(fn);
    return () => this.handlers.delete(fn);
  }

  connect(): void {
    this.closed = false;

    const apiBase =
      (import.meta.env?.VITE_API_URL as string | undefined) ?? "";

    let wsBase: string;

    if (apiBase) {
      wsBase = apiBase
        .replace(/^https:/, "wss:")
        .replace(/^http:/, "ws:");
    } else {
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      wsBase = `${scheme}://${location.host}`;
    }

    const url =
      `${wsBase}/ws?token=${encodeURIComponent(this.token)}`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.retries = 0;

      if (this.gameId) {
        this.subscribe(this.gameId);
      }

      this.startPing();
    };

    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WsMessage;

        this.handlers.forEach((handler) => {
          handler(msg);
        });
      } catch {
        // Ignore malformed WebSocket frames.
      }
    };

    this.ws.onclose = () => {
      this.stopPing();

      if (!this.closed) {
        const backoff = Math.min(
          2000,
          300 * 2 ** this.retries,
        );

        this.retries += 1;

        setTimeout(() => {
          this.connect();
        }, backoff);
      }
    };

    this.ws.onerror = () => {
      // Connection errors are handled by onclose.
    };
  }

  subscribe(gameId: string): void {
    this.gameId = gameId;

    this.send({
      type: "subscribe",
      game_id: gameId,
    });
  }

  sendAction(
    gameId: string,
    action: {
      type: string;
      card?: string;
      trump?: string;
      request_id: string;
    },
  ): void {
    this.send({
      type: "game.action",
      game_id: gameId,
      action,
    });
  }

  private send(payload: unknown): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload));
    }
  }

  private startPing(): void {
    this.stopPing();

    this.pingTimer = window.setInterval(() => {
      this.send({
        type: "ping",
        ts: Date.now(),
      });
    }, 25000);
  }

  private stopPing(): void {
    if (this.pingTimer !== null) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  close(): void {
    this.closed = true;
    this.stopPing();
    this.ws?.close();
  }
}}
