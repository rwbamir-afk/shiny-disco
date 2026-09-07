/**
 * Thin REST client. Authentication is a Bearer access token. Errors are typed
 * and surfaced as safe messages (never server stack traces).
 */

const BASE = (import.meta.env?.VITE_API_URL as string | undefined) ?? "";

export class ApiError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type HttpOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string | null;
};

export async function api<T>(
  path: string,
  opts: HttpOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (opts.token) {
    headers.Authorization = `Bearer ${opts.token}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    method: opts.method ?? (opts.body ? "POST" : "GET"),
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });

  const text = await res.text();

  let data: unknown = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    const err =
      (data as {
        detail?: string;
        error?: string;
        code?: string;
      }) ?? {};

    throw new ApiError(
      res.status,
      err.code ?? "http_error",
      err.detail ?? err.error ?? `HTTP ${res.status}`,
    );
  }

  return data as T;
}

export const apiUrl = (path: string) => `${BASE}${path}`;
