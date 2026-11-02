import { useState } from "react";
import { formatINR } from "../../api";

type Point = { day: string; orders: number; revenue: number };
const short = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

// One series, so no legend: the heading names it. Bars are thin with rounded tops, sit on the
// baseline with a 2px gap, and each has a hover/focus tooltip. A table copy serves screen readers.
export default function RevenueChart({ data }: { data: Point[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.revenue), 1);
  const H = 160;

  return (
    <figure className="chart">
      <figcaption className="chart-title">Revenue, last 14 days</figcaption>
      <div className="chart-plot" role="img" aria-label={`Daily revenue for the last 14 days, peaking at ${formatINR(max)}`}>
        <div className="chart-gridline" style={{ bottom: H }}><span>{formatINR(max)}</span></div>
        <div className="chart-gridline" style={{ bottom: 0 }}><span>₹0</span></div>
        <div className="chart-bars" style={{ height: H }}>
          {data.map((d, i) => (
            <button
              key={d.day}
              className="chart-col"
              aria-label={`${short(d.day)}: ${formatINR(d.revenue)} from ${d.orders} orders`}
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)} onBlur={() => setHover(null)}
            >
              <span className="chart-bar" style={{ height: d.revenue ? Math.max(3, (d.revenue / max) * H) : 0 }} />
              {hover === i && (
                <span className="chart-tip" role="tooltip">
                  <strong>{short(d.day)}</strong>{formatINR(d.revenue)} · {d.orders} {d.orders === 1 ? "order" : "orders"}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="chart-x">
          <span>{short(data[0].day)}</span><span>{short(data[data.length - 1].day)}</span>
        </div>
      </div>
      <table className="sr-only">
        <caption>Revenue by day</caption>
        <thead><tr><th>Day</th><th>Orders</th><th>Revenue</th></tr></thead>
        <tbody>{data.map((d) => <tr key={d.day}><td>{short(d.day)}</td><td>{d.orders}</td><td>{formatINR(d.revenue)}</td></tr>)}</tbody>
      </table>
    </figure>
  );
}
