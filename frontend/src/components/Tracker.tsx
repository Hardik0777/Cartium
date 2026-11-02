import type { ItemStatus } from "../api";

const STEPS: { key: ItemStatus; label: string }[] = [
  { key: "placed", label: "Placed" },
  { key: "packed", label: "Packed" },
  { key: "shipped", label: "Shipped" },
  { key: "delivered", label: "Delivered" },
];

// A real sequence, so the steps are drawn in order with the reached ones filled in.
export default function Tracker({ status }: { status: ItemStatus | "pending_payment" }) {
  if (status === "cancelled") return <p className="error">Cancelled</p>;
  const reached = STEPS.findIndex((s) => s.key === status);
  return (
    <ol className="tracker" aria-label={`Status: ${status}`}>
      {STEPS.map((s, i) => (
        <li key={s.key} className={i <= reached ? "done" : ""} aria-current={i === reached ? "step" : undefined}>
          <span className="dot" aria-hidden="true" />
          {s.label}
        </li>
      ))}
    </ol>
  );
}
