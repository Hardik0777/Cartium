export default function Stars({ value, count, size = "sm" }: { value: number; count?: number; size?: "sm" | "lg" }) {
  const label = count === 0 ? "No ratings yet" : `${value.toFixed(1)} out of 5${count !== undefined ? `, ${count} ratings` : ""}`;
  if (count === 0) return <span className={`stars stars-${size} muted`}>No ratings yet</span>;
  return (
    <span className={`stars stars-${size}`} aria-label={label} title={label}>
      <span className="stars-track" aria-hidden="true">
        ★★★★★
        <span className="stars-fill" style={{ width: `${(value / 5) * 100}%` }}>★★★★★</span>
      </span>
      <span className="stars-num">{value.toFixed(1)}</span>
      {count !== undefined && <span className="muted">({count})</span>}
    </span>
  );
}
