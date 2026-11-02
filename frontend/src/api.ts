// Small fetch wrapper: adds the JWT, turns API errors into readable messages.
const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "cartium_token";

export const tokenStore = {
  get(): string | null {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set(token: string | null) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch { /* storage blocked: stay logged in for this tab only */ }
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function readableDetail(detail: unknown): string {
  // FastAPI validation errors arrive as a list of {loc, msg}.
  if (Array.isArray(detail)) {
    return detail.map((d) => String(d.msg).replace(/^Value error, /, "")).join(". ");
  }
  return typeof detail === "string" ? detail : "Something went wrong. Try again.";
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(0, "Can't reach the Cartium server. Check that the backend is running.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, readableDetail(data.detail));
  return data as T;
}

export type Role = "buyer" | "seller" | "admin";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  seller_status: "pending" | "approved" | "rejected" | "suspended" | null;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}
