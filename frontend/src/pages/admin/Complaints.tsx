import { useCallback, useEffect, useState } from "react";
import { api, json, type Complaint } from "../../api";

export default function Complaints() {
  const [status, setStatus] = useState("open");
  const [rows, setRows] = useState<Complaint[] | null>(null);
  const [replying, setReplying] = useState<number | null>(null);
  const [reply, setReply] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => { api<Complaint[]>(`/api/admin/complaints?status=${status}`).then(setRows); }, [status]);
  useEffect(() => { load(); }, [load]);

  async function resolve(c: Complaint) {
    try {
      await api(`/api/admin/complaints/${c.id}`, json({ reply }, "PATCH"));
      setReplying(null); setReply(""); setError(""); load();
    } catch (e) { setError((e as Error).message); }
  }

  return (
    <section className="seller-section">
      <div className="chips" role="tablist" aria-label="Complaint status">
        {[["open", "Open"], ["resolved", "Resolved"], ["all", "All"]].map(([v, l]) => (
          <button key={v} role="tab" aria-selected={status === v} className={status === v ? "chip chip-on" : "chip"} onClick={() => setStatus(v)}>{l}</button>
        ))}
      </div>
      {rows?.length === 0 && <div className="empty"><strong>No complaints here.</strong></div>}
      <ul className="review-list">
        {rows?.map((c) => (
          <li key={c.id}>
            <div className="review-head">
              <strong>{c.subject}</strong>
              <span className="muted">{c.buyer_name} · order #{c.order_id} · {new Date(c.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}</span>
            </div>
            <p>{c.message}</p>
            {c.admin_reply && <p className="seller-reply"><strong>Reply:</strong> {c.admin_reply}</p>}
            {c.status === "open" && (replying === c.id ? (
              <div className="review-form">
                <textarea autoFocus rows={3} placeholder="Your reply to the buyer. Sending it resolves the complaint." value={reply} onChange={(e) => setReply(e.target.value)} />
                {error && <p className="error">{error}</p>}
                <div className="actions">
                  <button className="btn btn-small" onClick={() => resolve(c)}>Reply and resolve</button>
                  <button className="link-button" onClick={() => setReplying(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <button className="link-button" onClick={() => setReplying(c.id)}>Reply</button>
            ))}
          </li>
        ))}
      </ul>
    </section>
  );
}
