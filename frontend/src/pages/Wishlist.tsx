import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ProductCard } from "../api";
import ProductTile from "../components/ProductTile";

export default function Wishlist() {
  const [items, setItems] = useState<ProductCard[] | null>(null);

  useEffect(() => { api<ProductCard[]>("/api/account/wishlist").then(setItems).catch(() => setItems([])); }, []);

  async function remove(id: number) {
    setItems((prev) => prev?.filter((p) => p.id !== id) ?? null);
    await api(`/api/account/wishlist/${id}`, { method: "DELETE" }).catch(() => {});
  }

  if (!items) return <p className="muted">Loading…</p>;
  return (
    <section>
      <h1>Your wishlist</h1>
      {items.length === 0 ? (
        <div className="empty">
          <strong>Nothing saved yet.</strong>
          <p className="muted">Tap “Save to wishlist” on any product to keep it here. <Link to="/">Browse the store</Link></p>
        </div>
      ) : (
        <div className="grid">
          {items.map((p) => (
            <div key={p.id} className="wish-item">
              <ProductTile product={p} />
              <button className="link-button" onClick={() => remove(p.id)}>Remove</button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
