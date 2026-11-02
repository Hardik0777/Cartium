import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, formatINR, json, type CartDetail } from "../api";
import { useCarts } from "../cart";
import ProductImage from "../components/ProductImage";

export default function Cart() {
  const { carts, refresh } = useCarts();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [cart, setCart] = useState<CartDetail | null>(null);
  const [error, setError] = useState("");
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [rename, setRename] = useState("");

  const selected = Number(params.get("id")) || carts.find((c) => c.is_active)?.id;

  const load = useCallback(async () => {
    if (!selected) return;
    try { setCart(await api<CartDetail>(`/api/cart?cart_id=${selected}`)); setError(""); }
    catch (e) { setError((e as Error).message); }
  }, [selected]);

  useEffect(() => { load(); }, [load]);

  // Every change returns the updated cart; refresh the nav badge too.
  async function act(promise: Promise<CartDetail | unknown>) {
    setError("");
    try {
      const res = await promise;
      if (res && typeof res === "object" && "lines" in res) setCart(res as CartDetail); else await load();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function createCart(e: FormEvent) {
    e.preventDefault();
    try {
      const c = await api<{ id: number }>("/api/cart/carts", json({ name: newName, activate: true }));
      setNewName(""); setCreating(false);
      await refresh();
      setParams({ id: String(c.id) });
    } catch (err) { setError((err as Error).message); }
  }

  async function saveRename(e: FormEvent) {
    e.preventDefault();
    if (!cart) return;
    try {
      await api(`/api/cart/carts/${cart.id}`, json({ name: rename }, "PATCH"));
      setRenaming(false); await refresh(); await load();
    } catch (err) { setError((err as Error).message); }
  }

  async function deleteCart() {
    if (!cart) return;
    await api(`/api/cart/carts/${cart.id}`, { method: "DELETE" });
    setCart(null); setParams({}); await refresh();
  }

  async function makeActive() {
    if (!cart) return;
    await api(`/api/cart/carts/${cart.id}/activate`, { method: "PATCH" });
    await refresh(); await load();
  }

  return (
    <div className="cart-page">
      <h1>Your carts</h1>

      <div className="cart-tabs" role="tablist" aria-label="Carts">
        {carts.map((c) => (
          <button key={c.id} role="tab" aria-selected={c.id === selected}
                  className={c.id === selected ? "cart-tab on" : "cart-tab"} onClick={() => setParams({ id: String(c.id) })}>
            <span>{c.name}</span>
            <span className="cart-tab-count">{c.item_count}</span>
          </button>
        ))}
        {creating ? (
          <form className="inline-form" onSubmit={createCart}>
            <input autoFocus required maxLength={40} placeholder="e.g. Diwali gifts" value={newName}
                   onChange={(e) => setNewName(e.target.value)} aria-label="New cart name" />
            <button className="btn btn-small">Create</button>
            <button type="button" className="link-button" onClick={() => setCreating(false)}>Cancel</button>
          </form>
        ) : (
          <button className="cart-tab cart-tab-new" onClick={() => setCreating(true)}>+ New cart</button>
        )}
      </div>

      {error && <p className="error" role="alert">{error}</p>}

      {cart && (
        <div className="cart-body">
          <section>
            <div className="cart-head">
              {renaming ? (
                <form className="inline-form" onSubmit={saveRename}>
                  <input autoFocus required maxLength={40} value={rename} onChange={(e) => setRename(e.target.value)} aria-label="Cart name" />
                  <button className="btn btn-small">Save</button>
                  <button type="button" className="link-button" onClick={() => setRenaming(false)}>Cancel</button>
                </form>
              ) : (
                <h2>{cart.name}</h2>
              )}
              <div className="cart-tools">
                {cart.is_active ? <span className="pill">New items go here</span>
                  : <button className="link-button" onClick={makeActive}>Add new items here</button>}
                {!renaming && <button className="link-button" onClick={() => { setRename(cart.name); setRenaming(true); }}>Rename</button>}
                <button className="link-button" onClick={deleteCart}>Delete cart</button>
              </div>
            </div>

            {cart.lines.length === 0 ? (
              <div className="empty">
                <strong>This cart is empty.</strong>
                <p className="muted"><Link to="/">Browse the store</Link> and add items to “{cart.name}”.</p>
              </div>
            ) : (
              <ul className="lines">
                {cart.lines.map((line) => (
                  <li key={line.id} className={line.problem ? "line line-problem" : "line"}>
                    <Link to={`/products/${line.product.id}`} className="line-img"><ProductImage product={line.product} /></Link>
                    <div className="line-info">
                      <Link to={`/products/${line.product.id}`} className="line-name">{line.product.name}</Link>
                      <span className="muted">{formatINR(line.product.price)} each · sold by {line.product.seller.name}</span>
                      {line.problem && <span className="error">{line.problem}</span>}
                      <div className="line-controls">
                        <label className="mini-field">
                          Qty
                          <select value={line.quantity} onChange={(e) => act(api(`/api/cart/${line.id}`, json({ quantity: Number(e.target.value) }, "PATCH")))}>
                            {Array.from({ length: Math.max(line.quantity, Math.min(10, line.product.stock)) }, (_, i) => i + 1)
                              .map((n) => <option key={n}>{n}</option>)}
                          </select>
                        </label>
                        {carts.length > 1 && (
                          <label className="mini-field">
                            Move to
                            <select value="" onChange={(e) => e.target.value && act(api(`/api/cart/${line.id}`, json({ cart_id: Number(e.target.value) }, "PATCH")))}>
                              <option value="">Choose…</option>
                              {carts.filter((c) => c.id !== cart.id).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                            </select>
                          </label>
                        )}
                        <button className="link-button" onClick={() => act(api(`/api/cart/${line.id}`, { method: "DELETE" }))}>Remove</button>
                      </div>
                    </div>
                    <strong className="line-total">{formatINR(line.line_total)}</strong>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {cart.lines.length > 0 && (
            <aside className="summary">
              <h2>Summary</h2>
              <dl>
                <dt>Items ({cart.item_count})</dt><dd>{formatINR(cart.subtotal)}</dd>
                <dt>Delivery</dt><dd>{cart.shipping_fee === 0 ? "Free" : formatINR(cart.shipping_fee)}</dd>
                <dt className="summary-total">Total</dt><dd className="summary-total">{formatINR(cart.total)}</dd>
              </dl>
              {cart.shipping_fee > 0 && <p className="muted small">Free delivery on orders over ₹499.</p>}
              <button className="btn btn-block" disabled={!cart.can_checkout} onClick={() => navigate(`/checkout/${cart.id}`)}>
                Check out this cart
              </button>
              {!cart.can_checkout && <p className="muted small">Fix the highlighted items to check out.</p>}
            </aside>
          )}
        </div>
      )}
    </div>
  );
}
