import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Role } from "../api";
import { homeFor, useAuth } from "../auth";
import AuthShell from "../components/AuthShell";
import GoogleSignIn from "../components/GoogleSignIn";

const ROLES: { value: Role; title: string; text: string }[] = [
  { value: "buyer", title: "Shop", text: "Browse, build carts and order" },
  { value: "seller", title: "Sell", text: "List products once an admin approves you" },
];

export default function Signup() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "buyer" as Role });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const user = await signup(form.name, form.email, form.password, form.role);
      navigate(homeFor(user.role), { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Create your account">
      <GoogleSignIn />
      <form onSubmit={submit} className="form">
        <fieldset className="role-picker">
          <legend>I want to</legend>
          {ROLES.map((r) => (
            <label key={r.value} className={form.role === r.value ? "role-option selected" : "role-option"}>
              <input type="radio" name="role" value={r.value} checked={form.role === r.value} onChange={set("role")} />
              <strong>{r.title}</strong>
              <span>{r.text}</span>
            </label>
          ))}
        </fieldset>
        <label>Full name<input required autoComplete="name" value={form.name} onChange={set("name")} /></label>
        <label>Email<input type="email" required autoComplete="email" value={form.email} onChange={set("email")} /></label>
        <label>
          Password
          <input type="password" required minLength={8} maxLength={72} autoComplete="new-password" value={form.password} onChange={set("password")} />
          <span className="hint">At least 8 characters, with a letter and a number</span>
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button className="btn" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
      </form>
      <p className="muted">Already have an account? <Link to="/login">Log in</Link></p>
    </AuthShell>
  );
}
