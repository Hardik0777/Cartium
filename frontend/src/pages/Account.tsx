import { useAuth } from "../auth";

const ROLE_LABEL = { buyer: "Shopper", seller: "Seller", admin: "Administrator" };

export default function Account() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <section className="panel">
      <h1>Your account</h1>
      <dl className="details">
        <dt>Name</dt><dd>{user.name}</dd>
        <dt>Email</dt><dd>{user.email}</dd>
        <dt>Account type</dt><dd>{ROLE_LABEL[user.role]}</dd>
        <dt>Member since</dt><dd>{new Date(user.created_at).toLocaleDateString("en-IN", { dateStyle: "long" })}</dd>
      </dl>
    </section>
  );
}
