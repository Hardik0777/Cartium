import { useAuth } from "../auth";

const STATUS = {
  pending: { title: "Your seller account is under review", text: "An admin will approve it soon. You can list products once it's approved." },
  approved: { title: "Your shop is live", text: "Listings, stock and orders will appear here in a later update." },
  rejected: { title: "Your seller application wasn't approved", text: "Contact support if you think this is a mistake." },
  suspended: { title: "Your shop is suspended", text: "Your listings are hidden until an admin restores your account." },
};

export default function SellerDashboard() {
  const { user } = useAuth();
  const s = STATUS[user?.seller_status ?? "pending"];
  return (
    <section className="panel">
      <h1>Seller hub</h1>
      <div className={`status status-${user?.seller_status}`}>
        <strong>{s.title}</strong>
        <p>{s.text}</p>
      </div>
    </section>
  );
}
