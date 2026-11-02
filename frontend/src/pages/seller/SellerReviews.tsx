import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, json, type SellerReview } from "../../api";
import Stars from "../../components/Stars";

export default function SellerReviews() {
  const [reviews, setReviews] = useState<SellerReview[] | null>(null);
  const [replying, setReplying] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { api<SellerReview[]>("/api/seller/reviews").then(setReviews); }, []);

  async function send(e: FormEvent, r: SellerReview) {
    e.preventDefault();
    try {
      const updated = await api<SellerReview>(`/api/seller/reviews/${r.id}/response`, json({ response: text }));
      setReviews((prev) => prev?.map((x) => (x.id === r.id ? updated : x)) ?? null);
      setReplying(null); setError("");
    } catch (err) { setError((err as Error).message); }
  }

  if (!reviews) return <p className="muted">Loading…</p>;
  return (
    <section className="seller-section">
      {reviews.length === 0 && <div className="empty"><strong>No reviews yet.</strong><p className="muted">Reviews on your products will show up here.</p></div>}
      <ul className="review-list">
        {reviews.map((r) => (
          <li key={r.id}>
            <div className="review-head">
              <Stars value={r.rating} />
              <strong>{r.author}</strong>
              <span className="muted">on <Link to={`/products/${r.product_id}`}>{r.product_name}</Link></span>
            </div>
            {r.body && <p>{r.body}</p>}
            {replying === r.id ? (
              <form className="review-form" onSubmit={(e) => send(e, r)}>
                <textarea autoFocus rows={3} minLength={2} maxLength={1000} required value={text} onChange={(e) => setText(e.target.value)}
                          placeholder="Thank the buyer or explain how you'll fix the problem. Your reply is public." />
                {error && <p className="error">{error}</p>}
                <div className="actions">
                  <button className="btn btn-small">Post reply</button>
                  <button type="button" className="link-button" onClick={() => setReplying(null)}>Cancel</button>
                </div>
              </form>
            ) : (
              <>
                {r.seller_response && <p className="seller-reply"><strong>Your reply:</strong> {r.seller_response}</p>}
                <button className="link-button" onClick={() => { setReplying(r.id); setText(r.seller_response ?? ""); }}>
                  {r.seller_response ? "Edit reply" : "Reply"}
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
