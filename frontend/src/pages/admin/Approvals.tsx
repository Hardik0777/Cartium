import { useCallback, useEffect, useState } from "react";
import { api, formatINR, json, type AdminProduct, type AdminUser } from "../../api";
import ProductImage from "../../components/ProductImage";

export default function Approvals() {
  const [sellers, setSellers] = useState<AdminUser[] | null>(null);
  const [listings, setListings] = useState<AdminProduct[] | null>(null);
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api<AdminUser[]>("/api/admin/users?seller_status=pending").then(setSellers);
    api<AdminProduct[]>("/api/admin/products?status=pending").then(setListings);
  }, []);
  useEffect(() => { load(); }, [load]);

  async function seller(u: AdminUser, status: "approved" | "rejected") {
    await api(`/api/admin/users/${u.id}`, json({ seller_status: status }, "PATCH"));
    load();
  }

  async function moderate(p: AdminProduct, status: "approved" | "rejected") {
    setError("");
    try {
      await api(`/api/admin/products/${p.id}/moderation`, json({ status, note: status === "rejected" ? note : "" }, "PATCH"));
      setRejecting(null); setNote(""); load();
    } catch (e) { setError((e as Error).message); }
  }

  return (
    <div className="admin-cols">
      <section className="seller-section">
        <h2>New sellers ({sellers?.length ?? "…"})</h2>
        {sellers?.length === 0 && <p className="muted">No one is waiting.</p>}
        <ul className="lines">
          {sellers?.map((u) => (
            <li key={u.id} className="line line-plain">
              <div className="line-info">
                <span className="line-name">{u.name}</span>
                <span className="muted">{u.email} · signed up {new Date(u.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}</span>
              </div>
              <div className="row-actions">
                <button className="btn btn-small" onClick={() => seller(u, "approved")}>Approve</button>
                <button className="link-button" onClick={() => seller(u, "rejected")}>Reject</button>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <section className="seller-section">
        <h2>Listings to review ({listings?.length ?? "…"})</h2>
        {listings?.length === 0 && <p className="muted">Nothing to review.</p>}
        {error && <p className="error" role="alert">{error}</p>}
        <ul className="lines">
          {listings?.map((p) => (
            <li key={p.id} className="line review-item">
              <ProductImage product={{ name: p.name, image_url: p.image_url, category: { id: 0, name: p.category, slug: "" } }} />
              <div className="line-info">
                <span className="line-name">{p.name}</span>
                <span className="muted">{p.brand && `${p.brand} · `}{p.category} · {formatINR(p.price)} (MRP {formatINR(p.mrp)}) · {p.stock} in stock</span>
                <span className="muted">by {p.seller_name}</span>
                {p.description && <p className="small clamp">{p.description}</p>}
                {rejecting === p.id ? (
                  <div className="reject-box">
                    <textarea autoFocus rows={2} placeholder="Tell the seller what to fix (they'll see this)" value={note} onChange={(e) => setNote(e.target.value)} />
                    <div className="actions">
                      <button className="btn btn-small" onClick={() => moderate(p, "rejected")}>Send rejection</button>
                      <button className="link-button" onClick={() => { setRejecting(null); setNote(""); }}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div className="row-actions start">
                    <button className="btn btn-small" onClick={() => moderate(p, "approved")}>Approve</button>
                    <button className="link-button" onClick={() => setRejecting(p.id)}>Reject…</button>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
