import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, formatINR, type Order } from "../api";
import { useCarts } from "../cart";
import Tracker from "../components/Tracker";
import { orderDate } from "./Orders";

export default function OrderDetail() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { refresh } = useCarts();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => { api<Order>(`/api/orders/${id}`).then(setOrder).catch((e) => setError(e.message)); }, [id]);

  async function reorder() {
    const res = await api<{ cart_id: number; added: string[]; skipped: string[] }>(`/api/orders/${id}/reorder`, { method: "POST" });
    await refresh();
    if (res.added.length === 0) { setNote("None of these items are available right now."); return; }
    navigate(`/cart?id=${res.cart_id}`);
  }

  if (error) return <div className="empty"><strong>{error}</strong><p><Link to="/orders">Back to orders</Link></p></div>;
  if (!order) return <p className="muted">Loading…</p>;

  return (
    <article className="order-detail">
      {params.get("placed") && order.status === "paid" && (
        <div className="placed" role="status"><strong>Order placed.</strong> We've sent it to the sellers. Track it here.</div>
      )}
      <h1>Order #{order.id}</h1>
      <p className="muted">Placed {orderDate(order.created_at)} from “{order.cart_name}”</p>
      <Tracker status={order.progress} />

      <div className="cart-body">
        <section>
          <h2>Items</h2>
          <ul className="lines">
            {order.items.map((i) => (
              <li key={i.id} className="line line-plain">
                <div className="line-info">
                  {i.product_id ? <Link to={`/products/${i.product_id}`} className="line-name">{i.name}</Link> : <span className="line-name">{i.name}</span>}
                  <span className="muted">{i.quantity} × {formatINR(i.unit_price)} · sold by {i.seller_name}</span>
                  <span className={`status-chip status-${i.status}`}>{i.status[0].toUpperCase() + i.status.slice(1)}</span>
                </div>
                <strong className="line-total">{formatINR(i.unit_price * i.quantity)}</strong>
              </li>
            ))}
          </ul>
          <button className="btn btn-quiet" onClick={reorder}>Buy these again</button>
          {note && <p className="muted">{note}</p>}
        </section>
        <aside className="summary">
          <h2>Delivery</h2>
          <p className="ship"><strong>{order.ship_name}</strong> · {order.ship_phone}<br />{order.ship_address}</p>
          <dl>
            <dt>Items</dt><dd>{formatINR(order.subtotal)}</dd>
            <dt>Delivery</dt><dd>{order.shipping_fee === 0 ? "Free" : formatINR(order.shipping_fee)}</dd>
            <dt className="summary-total">Paid</dt><dd className="summary-total">{formatINR(order.total)}</dd>
          </dl>
        </aside>
      </div>
    </article>
  );
}
