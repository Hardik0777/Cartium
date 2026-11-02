import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, json, type AdminUser } from "../../api";
import { useAuth } from "../../auth";

export default function Users() {
  const { user: me } = useAuth();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback((query = q) => {
    const p = new URLSearchParams();
    if (query) p.set("q", query);
    if (role) p.set("role", role);
    api<AdminUser[]>(`/api/admin/users?${p}`).then(setUsers);
  }, [q, role]);
  useEffect(() => { load(); }, [role]); // eslint-disable-line react-hooks/exhaustive-deps

  async function change(u: AdminUser, body: Record<string, unknown>) {
    setError("");
    try {
      const updated = await api<AdminUser>(`/api/admin/users/${u.id}`, json(body, "PATCH"));
      setUsers((prev) => prev?.map((x) => (x.id === u.id ? updated : x)) ?? null);
    } catch (e) { setError((e as Error).message); }
  }

  return (
    <section className="seller-section">
      <form className="inline-form" onSubmit={(e: FormEvent) => { e.preventDefault(); load(); }} role="search">
        <input type="search" placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search users" />
        <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Role">
          <option value="">Everyone</option><option value="buyer">Buyers</option><option value="seller">Sellers</option><option value="admin">Admins</option>
        </select>
        <button className="btn btn-small">Search</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="table-wrap">
        <table className="data-table">
          <thead><tr><th>Name</th><th>Role</th><th>Activity</th><th>Status</th><th><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>
            {users?.map((u) => (
              <tr key={u.id} className={u.is_active ? "" : "row-banned"}>
                <td><strong>{u.name}</strong><br /><span className="muted small">{u.email}</span></td>
                <td>
                  <select value={u.role} disabled={u.id === me?.id} onChange={(e) => change(u, { role: e.target.value })} aria-label={`Role for ${u.name}`}>
                    <option value="buyer">Buyer</option><option value="seller">Seller</option><option value="admin">Admin</option>
                  </select>
                  {u.role === "seller" && (
                    <select value={u.seller_status ?? "pending"} onChange={(e) => change(u, { seller_status: e.target.value })} aria-label={`Seller status for ${u.name}`}>
                      <option value="pending">Pending</option><option value="approved">Approved</option>
                      <option value="rejected">Rejected</option><option value="suspended">Suspended</option>
                    </select>
                  )}
                </td>
                <td className="small">{u.role === "seller" ? `${u.listings} listings` : `${u.orders} orders`}</td>
                <td>{u.is_active ? <span className="status-chip status-delivered">Active</span> : <span className="status-chip status-cancelled">Banned</span>}</td>
                <td>
                  {u.id !== me?.id && (u.is_active
                    ? <button className="link-button danger" onClick={() => change(u, { is_active: false })}>Ban</button>
                    : <button className="link-button" onClick={() => change(u, { is_active: true })}>Unban</button>)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">Banning signs the person out everywhere immediately. Suspending a seller hides all their products.</p>
    </section>
  );
}
