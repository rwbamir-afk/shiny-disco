import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../lib/api";
import { getInitData } from "../lib/telegram";
import type { Session as SessionType } from "../lib/contracts";

const SESSION_KEY = "hokm.session";

interface SessionContextValue {
  session: SessionType | null;
  loading: boolean;
  error: string | null;
  authenticate: () => Promise<void>;
  refresh: () => Promise<void>;
  logout: () => void;
  accessToken: string | null;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionType | null>(() => {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      return raw ? (JSON.parse(raw) as SessionType) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function authenticate() {
    setLoading(true);
    setError(null);
    try {
      const initData = getInitData();
      if (!initData) {
        throw new Error("این برنامه باید از داخل تلگرام باز شود");
      }
      const data = await api<SessionType>("/api/v1/auth/telegram", { body: { init_data: initData } });
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
      setSession(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "خطا در ورود");
    } finally {
      setLoading(false);
    }
  }

  async function refresh() {
    if (!session) return;
    try {
      const data = await api<{ access_token: string; refresh_token: string }>("/api/v1/auth/refresh", {
        body: { refresh_token: session.tokens.refresh_token },
      });
      const next = { ...session, tokens: { access_token: data.access_token, refresh_token: data.refresh_token } };
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(next));
      setSession(next);
    } catch {
      logout();
    }
  }

  function logout() {
    sessionStorage.removeItem(SESSION_KEY);
    setSession(null);
  }

  useEffect(() => {
    if (!session) return;
    // Proactively refresh shortly before the access token expires.
    const min = 12 * 60 * 1000;
    const t = setTimeout(() => void refresh(), min);
    return () => clearTimeout(t);
  }, [session]);

  const accessToken = session?.tokens.access_token ?? null;

  return (
    <SessionContext.Provider value={{ session, loading, error, authenticate, refresh, logout, accessToken }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used within SessionProvider");
  return ctx;
}
