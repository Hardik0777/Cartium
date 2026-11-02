import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, json, type ProductDetail } from "../api";
import { useAuth } from "../auth";
import { useCarts } from "../cart";

export default function AddToCart({ product }: { product: ProductDetail }) {
  const { user } = useAuth();
  const { carts, active, refresh } = useCarts();
  const navigate = useNavigate();
  const location = useLocation();
  const [qty, setQty] = useState(1);
  const [cartId, setCartId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string; cartId?: number } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (active && cartId === null) setCartId(active.id); }, [active, cartId]);

  const max = Math.min(10, product.stock);
  if (product.stock <= 0) return null;
  if (user && user.role !== "buyer") return null; // sellers and admins don't shop

  async function add() {
    if (!user) { navigate("/login", { state: { from: location.pathname } }); return; }
    setBusy(true); setMessage(null);
    try {
      await api("/api/cart", json({ product_id: product.id, quantity: qty, cart_id: cartId ?? undefined }));
      await refresh();
      const name = carts.find((c) => c.id === cartId)?.name ?? "your cart";
      setMessage({ ok: true, text: `Added to ${name}.`, cartId: cartId ?? undefined });
    } catch (e) {
      setMessage({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="add-to-cart">
      <div className="add-row">
        <label className="mini-field">
          Qty
          <select value={qty} onChange={(e) => setQty(Number(e.target.value))}>
            {Array.from({ length: max }, (_, i) => i + 1).map((n) => <option key={n}>{n}</option>)}
          </select>
        </label>
        {carts.length > 1 && (
          <label className="mini-field">
            Cart
            <select value={cartId ?? ""} onChange={(e) => setCartId(Number(e.target.value))}>
              {carts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
        )}
        <button className="btn" onClick={add} disabled={busy}>{busy ? "Adding…" : "Add to cart"}</button>
      </div>
      {message && (
        <p className={message.ok ? "note-ok" : "error"} role="status">
          {message.text} {message.ok && <Link to={`/cart?id=${message.cartId}`}>View cart</Link>}
        </p>
      )}
    </div>
  );
}
