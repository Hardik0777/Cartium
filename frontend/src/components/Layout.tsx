import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <>
      <header className="topbar">
        <Link to="/" className="wordmark">Cartium</Link>
        <nav>
          {user?.role === "buyer" && <NavLink to="/wishlist">Wishlist</NavLink>}
          {user?.role === "seller" && <NavLink to="/seller">Seller hub</NavLink>}
          {user?.role === "admin" && <NavLink to="/admin">Admin</NavLink>}
          {user ? (
            <>
              <NavLink to="/account">{user.name.split(" ")[0]}</NavLink>
              <button className="link-button" onClick={async () => { await logout(); navigate("/"); }}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login">Log in</NavLink>
              <Link to="/signup" className="btn btn-small">Sign up</Link>
            </>
          )}
        </nav>
      </header>
      <main className="page">
        <Outlet />
      </main>
    </>
  );
}
