import type { ReactNode } from "react";
import { Link } from "react-router-dom";

// The left panel shows Cartium's signature idea: several named carts on the go at once.
const CARTS = [
  { name: "Groceries", items: 12, total: "₹2,340" },
  { name: "Diwali gifts", items: 5, total: "₹8,950" },
  { name: "Office setup", items: 3, total: "₹14,499" },
];

export default function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="auth">
      <aside className="auth-panel" aria-hidden="true">
        <Link to="/" className="wordmark wordmark-light">Cartium</Link>
        <div className="cart-stack">
          {CARTS.map((c) => (
            <div key={c.name} className="cart-tag">
              <span className="cart-name">{c.name}</span>
              <span className="cart-meta">{c.items} items</span>
              <span className="cart-total">{c.total}</span>
            </div>
          ))}
        </div>
        <p className="auth-pitch">One account, as many carts as you need. Shop, sell or run the store.</p>
      </aside>
      <section className="auth-form">
        <div className="auth-inner">
          <h1>{title}</h1>
          {children}
        </div>
      </section>
    </div>
  );
}
