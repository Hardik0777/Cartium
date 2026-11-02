import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatINR, type Listing } from "../../api";
import ProductImage from "../../components/ProductImage";
import ListingForm from "./ListingForm";

const STATUS: Record<Listing["status"], string> = {
  approved: "Live", pending: "Waiting for review", rejected: "Rejected, edit to resubmit", removed: "Removed by admin",
};

export default function Listings() {
  const [listings, setListings] = useState<Listing[] | null>(null);
  const [editing, setEditing] = useState<Listing | "new" | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const load = useCallback(() => { api<Listing[]>("/api/seller/products").then(setListings); }, []);
  useEffect(() => { load(); }, [load]);

  async function remove(id: number) {
    await api(`/api/seller/products/${id}`, { method: "DELETE" });
    setConfirmDelete(null); load();
  }

  if (editing) {
    return <ListingForm listing={editing === "new" ? undefined : editing}
                        onDone={() => { setEditing(null); load(); }} onCancel={() => setEditing(null)} />;
  }
  if (!listings) return <p className="muted">Loading…</p>;

  return (
    <section className="seller-section">
      <div className="section-head">
        <h2>Your products ({listings.length})</h2>
        <button className="btn btn-small" onClick={() => setEditing("new")}>Add a product</button>
      </div>
      {listings.length === 0 && <div className="empty"><strong>No products yet.</strong><p className="muted">Add your first product to start selling.</p></div>}
      <ul className="listing-rows">
        {listings.map((l) => {
          const low = l.status === "approved" && l.stock <= l.low_stock_threshold;
          return (
            <li key={l.id} className="listing-row">
              <ProductImage product={{ name: l.name, image_url: l.image_url, category: { id: l.category_id, name: l.category_name, slug: l.category_slug } }} />
              <div className="listing-main">
                {l.status === "approved" ? <Link to={`/products/${l.id}`} className="line-name">{l.name}</Link> : <span className="line-name">{l.name}</span>}
                <span className="muted">{l.category_name} · {formatINR(l.price)} <s>{formatINR(l.mrp)}</s> · {l.units_sold} sold</span>
                <span className={`listing-status listing-${l.status}`}>{STATUS[l.status]}</span>
              </div>
              <div className={low ? "stock-cell stock-cell-low" : "stock-cell"}>
                <strong>{l.stock}</strong>
                <span>{l.stock === 0 ? "out of stock" : low ? "running low" : "in stock"}</span>
              </div>
              <div className="row-actions">
                {l.status !== "removed" && <button className="link-button" onClick={() => setEditing(l)}>Edit</button>}
                {confirmDelete === l.id ? (
                  <>
                    <button className="link-button danger" onClick={() => remove(l.id)}>Yes, delete</button>
                    <button className="link-button" onClick={() => setConfirmDelete(null)}>Keep</button>
                  </>
                ) : (
                  <button className="link-button" onClick={() => setConfirmDelete(l.id)}>Delete</button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
