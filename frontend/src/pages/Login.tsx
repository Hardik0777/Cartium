import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { homeFor, useAuth } from "../auth";
import AuthShell from "../components/AuthShell";
import GoogleSignIn from "../components/GoogleSignIn";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const user = await login(email, password);
      navigate(from ?? homeFor(user.role), { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Log in to Cartium">
      <GoogleSignIn from={from} />
      <form onSubmit={submit} className="form">
        <label>Email<input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password<input type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
      </form>
      <p className="muted">New here? <Link to="/signup">Create an account</Link></p>
    </AuthShell>
  );
}
