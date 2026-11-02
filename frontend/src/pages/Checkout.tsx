import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, api, formatINR, json, type Address, type CartDetail, type Checkout as CheckoutInfo, type Order } from "../api";
import { useCarts } from "../cart";
import AddressForm from "../components/AddressForm";
import { PaymentClosed, pay } from "../razorpay";

export default function Checkout() {
  const { cartId } = useParams();
  const navigate = useNavigate();
  const { refresh } = useCarts();
  const [cart, setCart] = useState<CartDetail | null>(null);
  const [addresses, setAddresses] = useState<Address[] | null>(null);
  const [addressId, setAddressId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<CartDetail>(`/api/cart?cart_id=${cartId}`).then(setCart).catch((e) => setError(e.message));
    api<Address[]>("/api/account/addresses").then((list) => {
      setAddresses(list);
      setAddressId(list.find((a) => a.is_default)?.id ?? list[0]?.id ?? null);
      setAdding(list.length === 0);
    });
  }, [cartId]);

  async function placeOrder() {
    if (!cart || !addressId) return;
    setBusy(true); setError("");
    let checkout: CheckoutInfo | null = null;
    let paid = false;
    try {
      checkout = await api<CheckoutInfo>("/api/orders/razorpay/create", json({ cart_id: cart.id, address_id: addressId }));
      const result = await pay(checkout);
      paid = true; // from here on, money has moved: never cancel the order
      const order = await api<Order>("/api/orders/razorpay/verify", json(result));
      await refresh();
      navigate(`/orders/${order.id}?placed=1`, { replace: true });
    } catch (e) {
      if (paid && e instanceof ApiError && e.status >= 400 && e.status < 500) {
        setError(e.message); // the server looked at the payment and explained what's wrong
      } else if (paid) {
        // We never heard back (network or server error). Money may have moved, so don't cancel.
        setError("Your payment went through, but we couldn't confirm it yet. Don't pay again; check Orders in a minute or contact support.");
      } else {
        if (checkout) {
          // Give the reserved stock back straight away instead of waiting for it to expire.
          await api(`/api/orders/${checkout.order_id}/cancel`, { method: "POST" }).catch(() => {});
        }
        setError(e instanceof PaymentClosed ? "Payment was cancelled. Your cart is unchanged." : (e as Error).message);
      }
      setBusy(false);
    }
  }

  if (error && !cart) return <div className="empty"><strong>{error}</strong><p><Link to="/cart">Back to carts</Link></p></div>;
  if (!cart || !addresses) return <p className="muted">Loading…</p>;

  return (
    <div className="checkout">
      <h1>Check out “{cart.name}”</h1>
      <div className="cart-body">
        <section className="checkout-main">
          <h2>Deliver to</h2>
          {addresses.length > 0 && (
            <div className="address-list" role="radiogroup" aria-label="Delivery address">
              {addresses.map((a) => (
                <label key={a.id} className={a.id === addressId ? "address on" : "address"}>
                  <input type="radio" name="address" checked={a.id === addressId} onChange={() => setAddressId(a.id)} />
                  <span>
                    <strong>{a.full_name}</strong> · {a.phone}<br />
                    {a.line1}{a.line2 && `, ${a.line2}`}, {a.city}, {a.state} {a.pincode}
                  </span>
                </label>
              ))}
            </div>
          )}
          {adding ? (
            <AddressForm
              onSaved={(a) => { setAddresses([...addresses, a]); setAddressId(a.id); setAdding(false); }}
              onCancel={addresses.length ? () => setAdding(false) : undefined}
            />
          ) : (
            <button className="link-button" onClick={() => setAdding(true)}>+ Add a new address</button>
          )}

          <h2>Items</h2>
          <ul className="checkout-items">
            {cart.lines.map((l) => (
              <li key={l.id}><span>{l.product.name} × {l.quantity}</span><span>{formatINR(l.line_total)}</span></li>
            ))}
          </ul>
        </section>

        <aside className="summary">
          <h2>Payment</h2>
          <dl>
            <dt>Items</dt><dd>{formatINR(cart.subtotal)}</dd>
            <dt>Delivery</dt><dd>{cart.shipping_fee === 0 ? "Free" : formatINR(cart.shipping_fee)}</dd>
            <dt className="summary-total">To pay</dt><dd className="summary-total">{formatINR(cart.total)}</dd>
          </dl>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn btn-block" disabled={busy || !addressId || !cart.can_checkout} onClick={placeOrder}>
            {busy ? "Waiting for payment…" : `Pay ${formatINR(cart.total)}`}
          </button>
          <p className="muted small">Secure payment by Razorpay. Items are held for you for 15 minutes while you pay.</p>
        </aside>
      </div>
    </div>
  );
}
