import { useEffect, useState } from "react";
import { api, formatINR, type AdminDashboardData } from "../../api";
import RevenueChart from "./RevenueChart";


export default function Overview({ goTo }: { goTo: (tab: string) => void }) {
  const [d, setD] = useState<AdminDashboardData | null>(null);
  useEffect(() => { api<AdminDashboardData>("/api/admin/dashboard").then(setD); }, []);
  if (!d) return <p className="muted">Loading…</p>;

  const queue = [
    { n: d.pending_sellers, label: d.pending_sellers === 1 ? "seller to approve" : "sellers to approve", tab: "approvals" },
    { n: d.pending_listings, label: d.pending_listings === 1 ? "listing to review" : "listings to review", tab: "approvals" },
    { n: d.refunds_requested, label: d.refunds_requested === 1 ? "refund to send" : "refunds to send", tab: "refunds" },
    { n: d.open_complaints, label: d.open_complaints === 1 ? "open complaint" : "open complaints", tab: "complaints" },
  ].filter((q) => q.n > 0);

  return (
    <div className="overview">
      {queue.length > 0 && (
        <div className="queue">
          {queue.map((q) => (
            <button key={q.label} className="todo" onClick={() => goTo(q.tab)}>
              <strong>{q.n} {q.label}</strong><span>Review</span>
            </button>
          ))}
        </div>
      )}

      <dl className="stats">
        <div><dt>Sales, all time</dt><dd>{formatINR(d.gmv)}</dd></div>
        <div><dt>Sales, 30 days</dt><dd>{formatINR(d.gmv_30d)}</dd></div>
        <div><dt>Paid orders</dt><dd>{d.paid_orders}</dd></div>
        <div><dt>Buyers</dt><dd>{d.buyers}</dd></div>
        <div><dt>Sellers</dt><dd>{d.sellers}</dd></div>
        <div><dt>New sign-ups, 7 days</dt><dd>{d.new_users_7d}</dd></div>
      </dl>

      <div className="overview-cols">
        <RevenueChart data={d.last_14_days} />
        <section>
          <h2>Worth a look</h2>
          {d.flags.length === 0 ? <p className="muted">Nothing unusual right now.</p> : (
            <ul className="flags">
              {d.flags.map((f, i) => (
                <li key={i} className={`flag flag-${f.severity}`}>
                  <span className="flag-label">{f.severity === "high" ? "⚠ Check soon" : "ℹ Review"}</span>
                  {f.message}
                </li>
              ))}
            </ul>
          )}
          <p className="muted small">Flags are simple rules (large orders, repeated unpaid checkouts, sellers cancelling often). They don't block anyone.</p>
        </section>
      </div>

      <section>
        <h2>Recent admin actions</h2>
        {d.recent_actions.length === 0 ? <p className="muted">No actions yet.</p> : (
          <ul className="plain-list audit">
            {d.recent_actions.map((a) => (
              <li key={a.id}>
                <span><strong>{a.admin_name}</strong> {a.target_type} #{a.target_id}: {a.action.startsWith("seller:") ? `seller ${a.action.split(":")[1]}` : a.action.replace("role:", "role ").replace("->", " → ")}{a.note && <span className="muted"> · “{a.note}”</span>}</span>
                <span className="muted">{new Date(a.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
