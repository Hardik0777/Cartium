import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, formatINR, json, type ChatTurn, type ProductCard } from "../api";
import { useAuth } from "../auth";
import { useCarts } from "../cart";
import ProductImage from "./ProductImage";

const SUGGESTIONS = ["Gift ideas under ₹1,000", "Where is my order?", "How much is delivery?", "Add Assam tea to my cart"];

export default function Assistant() {
  const { user } = useAuth();
  const { refresh } = useCarts();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [added, setAdded] = useState<Record<string, string>>({});
  const end = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  const isBuyer = user?.role === "buyer";

  useEffect(() => {
    if (open && isBuyer) api<ChatTurn[]>("/api/ai/history").then(setTurns).catch(() => {});
  }, [open, isBuyer]);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [turns, busy]);
  useEffect(() => { if (open) input.current?.focus(); }, [open]);

  if (user && !isBuyer) return null; // the assistant is for shoppers
  if (location.pathname === "/login" || location.pathname === "/signup") return null;

  async function send(message: string) {
    if (!message.trim() || busy) return;
    setError(""); setText(""); setBusy(true);
    setTurns((t) => [...t, { role: "user", text: message, products: [], orders: [], action: null, source: null }]);
    try {
      const reply = await api<ChatTurn>("/api/ai/chat", json({ message }));
      setTurns((t) => [...t, reply]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function addToCart(product: ProductCard, cartId: number | null, key: string) {
    try {
      await api("/api/cart", json({ product_id: product.id, quantity: 1, cart_id: cartId ?? undefined }));
      await refresh();
      setAdded((a) => ({ ...a, [key]: "Added" }));
    } catch (e) {
      setAdded((a) => ({ ...a, [key]: (e as Error).message }));
    }
  }

  async function clear() {
    await api("/api/ai/history", { method: "DELETE" });
    setTurns([]);
  }

  if (!open) {
    return (
      <button className="ask-fab" onClick={() => (user ? setOpen(true) : navigate("/login", { state: { from: location.pathname } }))}>
        <span className="ask-dot" aria-hidden="true" />Ask Cartium
      </button>
    );
  }

  return (
    <section className="ask-panel" role="dialog" aria-label="Cartium shopping assistant">
      <header className="ask-head">
        <div>
          <strong>Ask Cartium</strong>
          <span>Finds products, answers store questions, checks your orders</span>
        </div>
        <div className="ask-head-actions">
          {turns.length > 0 && <button className="link-button light" onClick={clear}>Clear</button>}
          <button className="ask-close" onClick={() => setOpen(false)} aria-label="Close assistant">×</button>
        </div>
      </header>

      <div className="ask-body" aria-live="polite">
        {turns.length === 0 && !busy && (
          <div className="ask-empty">
            <p>Ask in your own words, for example:</p>
            <div className="ask-suggestions">
              {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`ask-msg ask-${t.role}`}>
            <p>{t.text}</p>
            {t.source === "fallback" && <span className="ask-note">The AI is offline, so these are the closest matches.</span>}
            {t.orders.map((o) => (
              <Link key={o.id} to={`/orders/${o.id}`} className="ask-order" onClick={() => setOpen(false)}>
                <strong>Order #{o.id}</strong>
                <span>{o.progress.replace("_", " ")} · {o.items} {o.items === 1 ? "item" : "items"} · {formatINR(o.total)}</span>
              </Link>
            ))}
            {t.products.length > 0 && (
              <ul className="ask-products">
                {t.products.map((p) => {
                  const suggested = t.action?.product_id === p.id;
                  const key = `${i}-${p.id}`;
                  return (
                    <li key={p.id} className={suggested ? "ask-product suggested" : "ask-product"}>
                      <Link to={`/products/${p.id}`} onClick={() => setOpen(false)}><ProductImage product={p} /></Link>
                      <div>
                        <Link to={`/products/${p.id}`} className="ask-pname" onClick={() => setOpen(false)}>{p.name}</Link>
                        <span className="ask-price">{formatINR(p.price)}{p.discount_pct > 0 && <s>{formatINR(p.mrp)}</s>}</span>
                        {p.stock_label === "out_of_stock" ? <span className="small error">Out of stock</span> : added[key] ? (
                          <span className={added[key] === "Added" ? "note-ok small" : "error small"}>{added[key] === "Added" ? `Added to ${suggested && t.action?.cart_name ? t.action.cart_name : "your cart"}` : added[key]}</span>
                        ) : (
                          <button className={suggested ? "btn btn-small" : "link-button"} onClick={() => addToCart(p, suggested ? t.action!.cart_id : null, key)}>
                            {suggested && t.action?.cart_name ? `Add to ${t.action.cart_name}` : "Add to cart"}
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        ))}
        {busy && <div className="ask-msg ask-assistant ask-typing" aria-label="Assistant is typing"><span /><span /><span /></div>}
        {error && <p className="error" role="alert">{error}</p>}
        <div ref={end} />
      </div>

      <form className="ask-input" onSubmit={(e: FormEvent) => { e.preventDefault(); send(text); }}>
        <input ref={input} value={text} onChange={(e) => setText(e.target.value)} maxLength={1000}
               placeholder="Ask about products, delivery or your orders" aria-label="Message" />
        <button className="btn btn-small" disabled={busy || !text.trim()}>Send</button>
      </form>
    </section>
  );
}
