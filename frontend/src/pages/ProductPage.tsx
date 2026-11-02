import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, formatINR, type ProductDetail, type ReviewSummary } from "../api";
import { useAuth } from "../auth";
import ProductImage from "../components/ProductImage";
import Stars from "../components/Stars";

export default function ProductPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [reviews, setReviews] = useState<ReviewSummary | null>(null);
  const [error, setError] = useState("");

  const loadReviews = useCallback(() => {
    api<ReviewSummary>(`/api/reviews/product/${id}`).then(setReviews).catch(() => {});
  }, [id]);

  useEffect(() => {
    setProduct(null); setError("");
    api<ProductDetail>(`/api/products/${id}`).then(setProduct).catch((e) => setError(e.message));
    loadReviews();
  }, [id, user, loadReviews]);

  async function toggleWishlist() {
    if (!user) { navigate("/login", { state: { from: location.pathname } }); return; }
    if (!product) return;
    const saved = product.in_wishlist;
    setProduct({ ...product, in_wishlist: !saved }); // update instantly, undo if the request fails
    try {
      if (saved) await api(`/api/account/wishlist/${product.id}`, { method: "DELETE" });
      else await api("/api/account/wishlist", { method: "POST", body: JSON.stringify({ product_id: product.id }) });
    } catch {
      setProduct({ ...product, in_wishlist: saved });
    }
  }

  if (error) return <div className="empty"><strong>{error}</strong><p><Link to="/">Back to the store</Link></p></div>;
  if (!product) return <p className="muted">Loading…</p>;

  return (
    <article className="product">
      <Link to={`/?category=${product.category.slug}`} className="crumb">{product.category.name}</Link>
      <div className="product-main">
        <ProductImage product={product} size="large" />
        <div className="product-info">
          <span className="tile-brand">{product.brand}</span>
          <h1>{product.name}</h1>
          <Stars value={product.rating_avg} count={product.rating_count} size="lg" />
          <div className="price-row price-row-lg">
            <strong>{formatINR(product.price)}</strong>
            {product.discount_pct > 0 && (
              <>
                <s className="muted">MRP {formatINR(product.mrp)}</s>
                <span className="off">{product.discount_pct}% off</span>
              </>
            )}
          </div>
          <p className={`stock stock-${product.stock_label === "out_of_stock" ? "out" : product.stock_label === "low" ? "low" : "ok"}`}>
            {product.stock_label === "out_of_stock" ? "Out of stock" :
             product.stock_label === "low" ? `Only ${product.stock} left` : "In stock"}
          </p>
          <div className="actions">
            <button className={product.in_wishlist ? "btn btn-quiet saved" : "btn btn-quiet"} onClick={toggleWishlist} aria-pressed={product.in_wishlist}>
              {product.in_wishlist ? "♥ Saved to wishlist" : "♡ Save to wishlist"}
            </button>
          </div>
          <p className="muted">Sold by {product.seller.name}</p>
          <p className="description">{product.description}</p>
        </div>
      </div>
      {reviews && <Reviews productId={product.id} summary={reviews} onChange={() => { loadReviews(); api<ProductDetail>(`/api/products/${id}`).then(setProduct); }} />}
    </article>
  );
}

function Reviews({ productId, summary, onChange }: { productId: number; summary: ReviewSummary; onChange: () => void }) {
  const { user } = useAuth();
  const mine = summary.reviews.find((r) => r.is_mine);
  const [editing, setEditing] = useState(false);
  const [rating, setRating] = useState(mine?.rating ?? 0);
  const [body, setBody] = useState(mine?.body ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { setRating(mine?.rating ?? 0); setBody(mine?.body ?? ""); }, [mine?.id, mine?.rating, mine?.body]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!rating) { setError("Choose a star rating."); return; }
    setBusy(true); setError("");
    try {
      await api("/api/reviews", { method: "POST", body: JSON.stringify({ product_id: productId, rating, body }) });
      setEditing(false);
      onChange();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!mine) return;
    await api(`/api/reviews/${mine.id}`, { method: "DELETE" });
    setRating(0); setBody(""); onChange();
  }

  const showForm = user?.role === "buyer" && (!mine || editing);

  return (
    <section className="reviews">
      <h2>Ratings and reviews</h2>
      {summary.count > 0 && (
        <div className="dist">
          {[5, 4, 3, 2, 1].map((s) => {
            const n = summary.distribution[s] ?? 0;
            return (
              <div key={s} className="dist-row">
                <span>{s}★</span>
                <span className="dist-bar"><span style={{ width: `${(n / summary.count) * 100}%` }} /></span>
                <span className="muted">{n}</span>
              </div>
            );
          })}
        </div>
      )}

      {showForm && (
        <form className="review-form" onSubmit={submit}>
          <strong>{mine ? "Edit your review" : "Rate this product"}</strong>
          <div className="star-input" role="radiogroup" aria-label="Your rating">
            {[1, 2, 3, 4, 5].map((s) => (
              <button type="button" key={s} role="radio" aria-checked={rating === s} aria-label={`${s} star${s > 1 ? "s" : ""}`}
                      className={s <= rating ? "on" : ""} onClick={() => setRating(s)}>★</button>
            ))}
          </div>
          <textarea rows={3} maxLength={2000} placeholder="What did you like or dislike? (optional)" value={body} onChange={(e) => setBody(e.target.value)} />
          {error && <p className="error" role="alert">{error}</p>}
          <div className="actions">
            <button className="btn btn-small" disabled={busy}>{busy ? "Saving…" : mine ? "Save review" : "Post review"}</button>
            {editing && <button type="button" className="link-button" onClick={() => setEditing(false)}>Cancel</button>}
          </div>
        </form>
      )}
      {!user && <p className="muted"><Link to="/login">Log in</Link> to rate this product.</p>}

      {summary.reviews.length === 0 && <p className="muted">No reviews yet.</p>}
      <ul className="review-list">
        {summary.reviews.map((r) => (
          <li key={r.id}>
            <div className="review-head">
              <Stars value={r.rating} />
              <strong>{r.author}{r.is_mine && " (you)"}</strong>
              <span className="muted">{new Date(r.created_at).toLocaleDateString("en-IN", { dateStyle: "medium" })}</span>
            </div>
            {r.body && <p>{r.body}</p>}
            {r.seller_response && <p className="seller-reply"><strong>Seller replied:</strong> {r.seller_response}</p>}
            {r.is_mine && !editing && (
              <div className="actions">
                <button className="link-button" onClick={() => setEditing(true)}>Edit</button>
                <button className="link-button" onClick={remove}>Delete</button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
