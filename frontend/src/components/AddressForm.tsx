import { useState, type FormEvent } from "react";
import { api, json, type Address } from "../api";

const EMPTY = { full_name: "", phone: "", line1: "", line2: "", city: "", state: "", pincode: "", is_default: false };

export default function AddressForm({ onSaved, onCancel }: { onSaved: (a: Address) => void; onCancel?: () => void }) {
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const field = (k: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    try { onSaved(await api<Address>("/api/account/addresses", json(form))); setForm(EMPTY); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  return (
    <form className="form address-form" onSubmit={submit}>
      <label>Full name<input required autoComplete="name" value={form.full_name} onChange={field("full_name")} /></label>
      <label>Mobile number<input required inputMode="tel" autoComplete="tel" placeholder="10-digit mobile" value={form.phone} onChange={field("phone")} /></label>
      <label className="span-2">House, building, street<input required autoComplete="address-line1" value={form.line1} onChange={field("line1")} /></label>
      <label className="span-2">Area, landmark (optional)<input autoComplete="address-line2" value={form.line2} onChange={field("line2")} /></label>
      <label>City<input required autoComplete="address-level2" value={form.city} onChange={field("city")} /></label>
      <label>State<input required autoComplete="address-level1" value={form.state} onChange={field("state")} /></label>
      <label>PIN code<input required inputMode="numeric" maxLength={6} autoComplete="postal-code" value={form.pincode} onChange={field("pincode")} /></label>
      {error && <p className="error span-2" role="alert">{error}</p>}
      <div className="actions span-2">
        <button className="btn btn-small" disabled={busy}>{busy ? "Saving…" : "Save address"}</button>
        {onCancel && <button type="button" className="link-button" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}
