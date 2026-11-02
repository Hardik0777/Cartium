import { useCallback, useEffect, useState } from "react";
import { api, formatINR, json, type ItemStatus, type SellerOrderItem } from "../../api";

const FILTERS = [["open", "To do"], ["placed", "New"], ["packed", "Packed"], ["shipped", "Shipped"], ["delivered", "Delivered"], ["cancelled", "Cancelled"]] as const;
const ACTION: Partial<Record<ItemStatus, string>> = { packed: "Mark packed", shipped: "Mark shipped", delivered: "Mark delivered" };

export default function SellerOrders() {
  const [filter, setFilter] = useState("open");
  const [items, setItems] = useState<SellerOrderItem[] | null>(null);
  const [error, setError] = useState("");
  const [confirmCancel, setConfirmCancel] = useState<number | null>(null);

  const load = useCallback(() => {
    api<SellerOrderItem[]>(`/api/seller/orders?status_filter=${filter}`).then(setItems).catch((e) => setError(e.message));
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  async function move(item: SellerOrderItem, status: ItemStatus) {
    setError("");
    try {
      const updated = await api<SellerOrderItem>(`/api/seller/orders/items/${item.id}/status`, json({ status }, "PATCH"));
      setItems((prev) => prev?.map((i) => (i.id === item.id ? updated : i)) ?? null);
      setConfirmCancel(null);
    } catch (e) { setError((e as Error).message); }
  }

  return (
    <section className="seller-section">
      <div className="chips" role="tablist" aria-label="Order status">
        {FILTERS.map(([v, l]) => (
          <button key={v} role="tab" aria-selected={filter === v} className={filter === v ? "chip chip-on" : "chip"} onClick={() => setFilter(v)}>{l}</button>
        ))}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {items?.length === 0 && <div className="empty"><strong>Nothing here.</strong><p className="muted">{filter === "open" ? "You're all caught up." : "No items with this status."}</p></div>}
      <ul className="lines">
        {items?.map((i) => (
          <li key={i.id} className="line line-plain seller-order">
            <div className="line-info">
              <span className="line-name">{i.name} × {i.quantity}</span>
              <span className="muted">Order #{i.order_id} · {new Date(i.ordered_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })} · {formatINR(i.unit_price * i.quantity)}</span>
              <span className={`status-chip status-${i.status}`}>{i.status[0].toUpperCase() + i.status.slice(1)}</span>
              <p className="ship small"><strong>Ship to {i.ship_name}</strong> · {i.ship_phone}<br />{i.ship_address}</p>
            </div>
            <div className="row-actions">
              {i.next_statuses.filter((s) => s !== "cancelled").map((s) => (
                <button key={s} className="btn btn-small" onClick={() => move(i, s)}>{ACTION[s]}</button>
              ))}
              {i.next_statuses.includes("cancelled") && (confirmCancel === i.id ? (
                <span className="confirm">
                  Cancel and restock?
                  <button className="link-button danger" onClick={() => move(i, "cancelled")}>Yes, cancel</button>
                  <button className="link-button" onClick={() => setConfirmCancel(null)}>No</button>
                </span>
              ) : (
                <button className="link-button" onClick={() => setConfirmCancel(i.id)}>Cancel item</button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
