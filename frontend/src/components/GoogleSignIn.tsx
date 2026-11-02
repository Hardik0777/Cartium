import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Role } from "../api";
import { homeFor, useAuth, type ChooseRole } from "../auth";

declare global {
  interface Window {
    google?: { accounts: { id: {
      initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: string }) => void;
      renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
    } } };
  }
}

const SCRIPT = "https://accounts.google.com/gsi/client";

function loadScript(): Promise<void> {
  if (window.google?.accounts) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${SCRIPT}"]`);
    const s = (existing as HTMLScriptElement) ?? Object.assign(document.createElement("script"), { src: SCRIPT, async: true });
    s.addEventListener("load", () => resolve());
    s.addEventListener("error", () => reject(new Error("Couldn't load Google sign-in")));
    if (!existing) document.head.appendChild(s);
  });
}

// Shows Google's own button (Google requires its branding), then asks first-time users
// whether they want to shop or sell before creating their account.
export default function GoogleSignIn({ from }: { from?: string }) {
  const { googleSignIn } = useAuth();
  const navigate = useNavigate();
  const holder = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState(false);
  const [pending, setPending] = useState<{ credential: string; who: ChooseRole } | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handle(credential: string, role?: Role) {
    setError(""); setBusy(true);
    try {
      const res = await googleSignIn(credential, role);
      if ("needs_role" in res) { setPending({ credential, who: res }); return; }
      navigate(from ?? homeFor(res.role), { replace: true });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    api<{ google_client_id: string | null }>("/api/auth/config").then(async ({ google_client_id }) => {
      if (!google_client_id || cancelled) return;
      await loadScript();
      if (cancelled || !holder.current || !window.google) return;
      window.google.accounts.id.initialize({ client_id: google_client_id, callback: (r) => handle(r.credential) });
      window.google.accounts.id.renderButton(holder.current, {
        theme: "outline", size: "large", shape: "pill", text: "continue_with", width: holder.current.offsetWidth || 320,
      });
      setEnabled(true);
    }).catch(() => { /* no Google button; email sign-in still works */ });
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // The button's element stays mounted the whole time: Google draws into it once, so removing it
  // during the role step would leave no button if the person goes back.
  return (
    <>
      {pending && (
      <div className="google-role" role="group" aria-labelledby="google-role-title">
        <strong id="google-role-title">One more step, {pending.who.name.split(" ")[0]}</strong>
        <p className="muted small">Signing up as {pending.who.email}. What would you like to do on Cartium?</p>
        <div className="role-picker">
          <button className="role-option" disabled={busy} onClick={() => handle(pending.credential, "buyer")}>
            <strong>Shop</strong><span>Browse, build carts and order</span>
          </button>
          <button className="role-option" disabled={busy} onClick={() => handle(pending.credential, "seller")}>
            <strong>Sell</strong><span>List products once an admin approves you</span>
          </button>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="link-button" onClick={() => setPending(null)}>Use a different account</button>
      </div>
      )}
      <div className={enabled && !pending ? "google-block" : "google-block hidden"}>
        <div ref={holder} className="google-btn" />
        {error && !pending && <p className="error" role="alert">{error}</p>}
        {enabled && <div className="divider"><span>or use your email</span></div>}
      </div>
    </>
  );
}
