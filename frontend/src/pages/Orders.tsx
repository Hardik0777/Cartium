import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatINR, type Order } from "../api";
import Tracker from "../components/Tracker";

export const orderDate = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { dateStyle: "medium" });

export default function Orders() {
  const [orders, setOrders] = useState<Order[] | null>(null);
  useEffect(() => { api<Order[]>("/api/orders").then(setOrders).catch(() => setOrders([])); }, []);

  if (!orders) return <p className="muted">Loading…</p>;
  return (
    <section className="orders">
      <h1>Your orders</h1>
      {orders.length === 0 ? (
        <div className="empty"><strong>No orders yet.</strong><p className="muted"><Link to="/">Start shopping</Link></p></div>
      ) : (
        <ul className="order-list">
          {orders.map((o) => (
            <li key={o.id}>
              <Link to={`/orders/${o.id}`} className="order-card">
                <div className="order-top">
                  <strong>Order #{o.id}</strong>
                  <span className="muted">{orderDate(o.created_at)} · {o.cart_name}</span>
                  <strong className="order-total">{formatINR(o.total)}</strong>
                </div>
                <p className="muted order-names">{o.items.map((i) => `${i.name} × ${i.quantity}`).join(", ")}</p>
                <Tracker status={o.progress} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
