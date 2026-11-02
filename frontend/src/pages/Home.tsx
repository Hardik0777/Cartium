import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type Category, type ProductCard, type ProductPage } from "../api";
import { useAuth } from "../auth";
import ProductTile from "../components/ProductTile";

const SORTS = [
  ["relevance", "Best match"],
  ["newest", "Newest"],
  ["price_asc", "Price: low to high"],
  ["price_desc", "Price: high to low"],
  ["rating", "Top rated"],
  ["discount", "Biggest discount"],
] as const;

export default function Home() {
  const { user } = useAuth();
  // Filters live in the URL, so a filtered page can be bookmarked or shared.
  const [params, setParams] = useSearchParams();
  const [categories, setCategories] = useState<Category[]>([]);
  const [result, setResult] = useState<ProductPage | null>(null);
  const [recent, setRecent] = useState<ProductCard[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [minPrice, setMinPrice] = useState(params.get("min_price") ?? "");
  const [maxPrice, setMaxPrice] = useState(params.get("max_price") ?? "");

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v); else next.delete(k);
    }
    if (!("page" in changes)) next.delete("page"); // any filter change starts again at page 1
    setParams(next);
  };

  useEffect(() => { api<Category[]>("/api/categories").then(setCategories).catch(() => {}); }, []);

  useEffect(() => {
    if (user) api<ProductCard[]>("/api/account/recently-viewed").then((r) => setRecent(r.slice(0, 6))).catch(() => {});
    else setRecent([]);
  }, [user]);

  useEffect(() => {
    setError("");
    api<ProductPage>(`/api/products?${params.toString()}`)
      .then(setResult)
      .catch((e) => setError(e.message));
  }, [params]);

  const search = (e: FormEvent) => { e.preventDefault(); update({ q: query.trim() || null }); };
  const applyPrice = (e: FormEvent) => { e.preventDefault(); update({ min_price: minPrice || null, max_price: maxPrice || null }); };
  const active = params.get("category");
  const page = Number(params.get("page") ?? 1);
  const hasFilters = ["q", "category", "min_price", "max_price", "min_rating", "in_stock"].some((k) => params.get(k));

  return (
    <div className="store">
      <form className="searchbar" onSubmit={search} role="search">
        <input type="search" placeholder="Search for earbuds, kurtas, pressure cookers…" value={query}
               onChange={(e) => setQuery(e.target.value)} aria-label="Search products" />
        <button className="btn">Search</button>
      </form>

      <nav className="chips" aria-label="Categories">
        <button className={!active ? "chip chip-on" : "chip"} onClick={() => update({ category: null })}>All</button>
        {categories.map((c) => (
          <button key={c.slug} className={active === c.slug ? "chip chip-on" : "chip"} onClick={() => update({ category: c.slug })}>
            {c.name}
          </button>
        ))}
      </nav>

      {recent.length > 0 && !hasFilters && (
        <section className="recent">
          <h2>Pick up where you left off</h2>
          <div className="recent-row">
            {recent.map((p) => <Link key={p.id} to={`/products/${p.id}`} className="recent-item">{p.name}</Link>)}
          </div>
        </section>
      )}

      <div className="store-body">
        <aside className="filters">
          <form onSubmit={applyPrice} className="filter-group">
            <span className="filter-title">Price (₹)</span>
            <div className="price-inputs">
              <input type="number" min={0} placeholder="Min" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} aria-label="Minimum price" />
              <span>to</span>
              <input type="number" min={0} placeholder="Max" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} aria-label="Maximum price" />
            </div>
            <button className="btn btn-small btn-quiet">Apply price</button>
          </form>
          <fieldset className="filter-group">
            <legend className="filter-title">Customer rating</legend>
            {[4, 3].map((r) => (
              <label key={r} className="check">
                <input type="radio" name="rating" checked={params.get("min_rating") === String(r)}
                       onChange={() => update({ min_rating: String(r) })} />
                {r}★ and above
              </label>
            ))}
            <label className="check">
              <input type="radio" name="rating" checked={!params.get("min_rating")} onChange={() => update({ min_rating: null })} />
              Any rating
            </label>
          </fieldset>
          <label className="check filter-group">
            <input type="checkbox" checked={params.get("in_stock") === "true"} onChange={(e) => update({ in_stock: e.target.checked ? "true" : null })} />
            Hide out-of-stock items
          </label>
          {hasFilters && (
            <button className="link-button" onClick={() => { setQuery(""); setMinPrice(""); setMaxPrice(""); setParams(new URLSearchParams()); }}>
              Clear all filters
            </button>
          )}
        </aside>

        <section className="results">
          <div className="results-head">
            <span className="muted">
              {result ? `${result.total} ${result.total === 1 ? "product" : "products"}` : "Loading…"}
              {params.get("q") && <> for “{params.get("q")}”</>}
            </span>
            <label className="sort">
              Sort by
              <select value={params.get("sort") ?? "relevance"} onChange={(e) => update({ sort: e.target.value })}>
                {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
          </div>

          {error && <p className="error" role="alert">{error}</p>}
          {result && result.total === 0 && (
            <div className="empty">
              <strong>No products match these filters.</strong>
              <p className="muted">Try a different search term, or clear the filters to see everything.</p>
            </div>
          )}
          <div className="grid">{result?.items.map((p) => <ProductTile key={p.id} product={p} />)}</div>

          {result && result.pages > 1 && (
            <nav className="pager" aria-label="Pages">
              <button className="btn btn-small btn-quiet" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>Previous</button>
              <span className="muted">Page {page} of {result.pages}</span>
              <button className="btn btn-small btn-quiet" disabled={page >= result.pages} onClick={() => update({ page: String(page + 1) })}>Next</button>
            </nav>
          )}
        </section>
      </div>
    </div>
  );
}
