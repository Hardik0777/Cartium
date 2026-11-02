import { Link } from "react-router-dom";
import { useAuth } from "../auth";

export default function Home() {
  const { user } = useAuth();
  return (
    <section className="home">
      <h1>{user ? `Welcome back, ${user.name.split(" ")[0]}` : "Shop with a cart for every plan"}</h1>
      <p className="lede">
        Keep groceries, gifts and that new desk setup in separate carts, check out each one when you're ready,
        and ask the assistant when you can't decide.
      </p>
      {!user && (
        <div className="actions">
          <Link to="/signup" className="btn">Create an account</Link>
          <Link to="/login" className="btn btn-quiet">Log in</Link>
        </div>
      )}
      <p className="muted coming">The product catalog arrives in the next update.</p>
    </section>
  );
}
