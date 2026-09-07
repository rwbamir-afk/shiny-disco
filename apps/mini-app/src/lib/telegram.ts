/**
 * Telegram Mini App helpers.
 *
 * The client only reads the initData string provided by the Telegram webview and
 * hands it to the server for verification. It never fabricates identity.
 */
export interface TgWebApp {
  initData: string;
  initDataUnsafe?: Record<string, unknown>;
  ready: () => void;
  expand: () => void;
  openLink?: (url: string) => void;
  HapticFeedback?: { impactOccurred: (s: string) => void };
  colorScheme?: "light" | "dark";
}

declare global {
  interface Window {
    Telegram?: { WebApp: TgWebApp };
  }
}

export function getTelegram(): TgWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

export function getInitData(): string {
  const tg = getTelegram();
  return tg?.initData ?? "";
}

export function notifyReady(): void {
  getTelegram()?.ready();
  getTelegram()?.expand();
}

export function haptic(style: "light" | "medium" | "heavy" = "light"): void {
  getTelegram()?.HapticFeedback?.impactOccurred(style);
}
