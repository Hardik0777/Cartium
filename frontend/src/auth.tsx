import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, tokenStore, type AuthResponse, type Role, type User } from "./api";

export interface ChooseRole { needs_role: true; name: string; email: string }

interface AuthState {
  user: User | null;
  loading: boolean;
  googleSignIn: (credential: string, role?: Role) => Promise<User | ChooseRole>;
  login: (email: string, password: string) => Promise<User>;
  signup: (name: string, email: string, password: string, role: Role) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Restore the session on page load if a token is saved.
    if (!tokenStore.get()) { setLoading(false); return; }
    api<User>("/api/auth/me")
      .then(setUser)
      .catch(() => tokenStore.set(null))
      .finally(() => setLoading(false));
  }, []);

  const finish = (res: AuthResponse) => {
    tokenStore.set(res.access_token);
    setUser(res.user);
    return res.user;
  };

  const login = useCallback(async (email: string, password: string) =>
    finish(await api<AuthResponse>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) })), []);

  const signup = useCallback(async (name: string, email: string, password: string, role: Role) =>
    finish(await api<AuthResponse>("/api/auth/signup", {
      method: "POST", body: JSON.stringify({ name, email, password, role }),
    })), []);

  const googleSignIn = useCallback(async (credential: string, role?: Role) => {
    const res = await api<AuthResponse | ChooseRole>("/api/auth/oauth", { method: "POST", body: JSON.stringify({ credential, role }) });
    return "needs_role" in res ? res : finish(res);
  }, []);

  const logout = useCallback(async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* token may already be invalid */ }
    tokenStore.set(null);
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, login, signup, logout, googleSignIn }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export const homeFor = (role: Role) => ({ buyer: "/", seller: "/seller", admin: "/admin" })[role];
