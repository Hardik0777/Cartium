import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, formatINR, type SellerDashboardData } from "../api";
import { useAuth } from "../auth";
import Listings from "./seller/Listings";
import SellerOrders from "./seller/SellerOrders";
import SellerReviews from "./seller/SellerReviews";

const STATUS = {
  pending: { title: "Your seller account is under review", text: "An admin will approve it soon. You can list products once it's approved." },
  rejected: { title: "Your seller application wasn't approved", text: "Contact support if you think this is a mistake." },
  suspended: { title: "Your shop is suspended", text: "Your listings are hidden until an admin restores your account." },
};

const TABS = [["overview", "Overview"], ["products", "Products"], ["orders", "Orders"], ["reviews", "Reviews"]] as const;

export default function SellerDashboard() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "overview";

  if (user?.seller_status !== "approved") {
    const s = STATUS[(user?.seller_status ?? "pending") as keyof typeof STATUS];
    return (
      <section className="panel">
        <h1>Seller hub</h1>
        <div className={`status status-${user?.seller_status}`}><strong>{s.title}</strong><p>{s.text}</p></div>
      </section>
    );
  }

  return (
    <div className="seller">
      <h1>{user.name}</h1>
      <nav className="seller-tabs" role="tablist" aria-label="Seller hub">
        {TABS.map(([v, l]) => (
          <button key={v} role="tab" aria-selected={tab === v} className={tab === v ? "seller-tab on" : "seller-tab"} onClick={() => setParams({ tab: v })}>{l}</button>
        ))}
      </nav>
      {tab === "overview" && <Overview goTo={(t) => setParams({ tab: t })} />}
      {tab === "products" && <Listings />}
      {tab === "orders" && <SellerOrders />}
      {tab === "reviews" && <SellerReviews />}
    </div>
  );
}

function Overview({ goTo }: { goTo: (tab: string) => void }) {
  const [d, setD] = useState<SellerDashboardData | null>(null);
  useEffect(() => { api<SellerDashboardData>("/api/seller/dashboard").then(setD); }, []);
  if (!d) return <p className="muted">Loading…</p>;

  return (
    <div className="overview">
      {d.to_ship > 0 && (
        <button className="todo" onClick={() => goTo("orders")}>
          <strong>{d.to_ship} {d.to_ship === 1 ? "item needs" : "items need"} packing or shipping</strong>
          <span>Open orders</span>
        </button>
      )}
      <dl className="stats">
        <div><dt>Revenue</dt><dd>{formatINR(d.revenue)}</dd></div>
        <div><dt>Orders</dt><dd>{d.orders}</dd></div>
        <div><dt>Units sold</dt><dd>{d.units_sold}</dd></div>
        <div><dt>Average rating</dt><dd>{d.average_rating ? `${d.average_rating.toFixed(1)}★` : "None yet"}</dd></div>
        <div><dt>Live products</dt><dd>{d.live_listings}{d.pending_listings > 0 && <small> +{d.pending_listings} in review</small>}</dd></div>
      </dl>

      <div className="overview-cols">
        <section>
          <h2>Running low</h2>
          {d.low_stock.length === 0 ? <p className="muted">Every live product is well stocked.</p> : (
            <ul className="plain-list">
              {d.low_stock.map((p) => (
                <li key={p.id}>
                  <span>{p.name}</span>
                  <strong className={p.stock === 0 ? "error" : "stock-low"}>{p.stock === 0 ? "Out of stock" : `${p.stock} left`}</strong>
                </li>
              ))}
            </ul>
          )}
          {d.low_stock.length > 0 && <button className="link-button" onClick={() => goTo("products")}>Update stock</button>}
        </section>
        <section>
          <h2>Best sellers</h2>
          {d.top_products.length === 0 ? <p className="muted">Your sales will appear here.</p> : (
            <ol className="plain-list ranked">
              {d.top_products.map((t) => (
                <li key={t.id}><span>{t.name}</span><span className="muted">{t.units} sold · {formatINR(t.revenue)}</span></li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
