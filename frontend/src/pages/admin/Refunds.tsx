import { useCallback, useEffect, useState } from "react";
import { api, formatINR, json, type AdminRefund } from "../../api";

export default function Refunds() {
  const [status, setStatus] = useState("requested");
  const [rows, setRows] = useState<AdminRefund[] | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => { api<AdminRefund[]>(`/api/admin/refunds?status=${status}`).then(setRows); }, [status]);
  useEffect(() => { load(); }, [load]);

  async function decide(r: AdminRefund, action: "process" | "reject") {
    setBusy(r.id); setError("");
    try {
      await api(`/api/admin/refunds/${r.id}`, json({ action, note }, "PATCH"));
      setRejecting(null); setNote(""); load();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  }

  return (
    <section className="seller-section">
      <div className="chips" role="tablist" aria-label="Refund status">
        {[["requested", "To send"], ["processed", "Sent"], ["rejected", "Rejected"], ["all", "All"]].map(([v, l]) => (
          <button key={v} role="tab" aria-selected={status === v} className={status === v ? "chip chip-on" : "chip"} onClick={() => setStatus(v)}>{l}</button>
        ))}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {rows?.length === 0 && <div className="empty"><strong>Nothing here.</strong></div>}
      <ul className="lines">
        {rows?.map((r) => (
          <li key={r.id} className="line line-plain">
            <div className="line-info">
              <span className="line-name">{formatINR(r.amount)} to {r.buyer_name}</span>
              <span className="muted">Order #{r.order_id} · {r.reason}</span>
              <span className="muted small">{r.buyer_email} · payment {r.razorpay_payment_id ?? "none"}{r.razorpay_refund_id && ` · refund ${r.razorpay_refund_id}`}</span>
              {rejecting === r.id && (
                <div className="reject-box">
                  <textarea autoFocus rows={2} placeholder="Why is this refund rejected?" value={note} onChange={(e) => setNote(e.target.value)} />
                  <div className="actions">
                    <button className="btn btn-small" onClick={() => decide(r, "reject")}>Reject refund</button>
                    <button className="link-button" onClick={() => setRejecting(null)}>Cancel</button>
                  </div>
                </div>
              )}
            </div>
            {r.status === "requested" ? (
              rejecting !== r.id && (
                <div className="row-actions">
                  <button className="btn btn-small" disabled={busy === r.id} onClick={() => decide(r, "process")}>
                    {busy === r.id ? "Sending…" : `Refund ${formatINR(r.amount)}`}
                  </button>
                  <button className="link-button" onClick={() => setRejecting(r.id)}>Reject…</button>
                </div>
              )
            ) : (
              <span className={`status-chip ${r.status === "processed" ? "status-delivered" : "status-cancelled"}`}>
                {r.status === "processed" ? "Sent" : "Rejected"}
              </span>
            )}
          </li>
        ))}
      </ul>
      <p className="muted small">Refunds go back to the buyer's original payment method through Razorpay.</p>
    </section>
  );
}
