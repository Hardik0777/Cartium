import { useEffect, useState, type FormEvent } from "react";
import { api, json, mediaUrl, uploadPhoto, type Category, type Listing } from "../../api";

type Form = {
  name: string; brand: string; description: string; category_id: string;
  price: string; mrp: string; stock: string; low_stock_threshold: string; image_url: string | null;
};

const fromListing = (l?: Listing): Form => ({
  name: l?.name ?? "", brand: l?.brand ?? "", description: l?.description ?? "",
  category_id: l ? String(l.category_id) : "", price: l ? String(l.price) : "", mrp: l ? String(l.mrp) : "",
  stock: l ? String(l.stock) : "", low_stock_threshold: l ? String(l.low_stock_threshold) : "5", image_url: l?.image_url ?? null,
});

export default function ListingForm({ listing, onDone, onCancel }: { listing?: Listing; onDone: () => void; onCancel: () => void }) {
  const [form, setForm] = useState<Form>(fromListing(listing));
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => { api<Category[]>("/api/categories").then(setCategories); }, []);
  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm({ ...form, [k]: e.target.value });

  const price = Number(form.price), mrp = Number(form.mrp);
  const discount = price > 0 && mrp > price ? Math.round(((mrp - price) / mrp) * 100) : 0;

  async function pickPhoto(file: File | undefined) {
    if (!file) return;
    setUploading(true); setError("");
    try { setForm({ ...form, image_url: await uploadPhoto(file) }); }
    catch (e) { setError((e as Error).message); }
    finally { setUploading(false); }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError("");
    const body = {
      ...form, category_id: Number(form.category_id), price, mrp,
      stock: Number(form.stock), low_stock_threshold: Number(form.low_stock_threshold),
    };
    try {
      if (listing) await api(`/api/seller/products/${listing.id}`, json(body, "PATCH"));
      else await api("/api/seller/products", json(body));
      onDone();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form className="form listing-form" onSubmit={submit}>
      <h2 className="span-2">{listing ? `Edit “${listing.name}”` : "Add a product"}</h2>
      {!listing && <p className="muted span-2">New products appear in the store once an admin approves them.</p>}

      <div className="photo-field span-2">
        <div className="photo-preview">
          {form.image_url ? <img src={mediaUrl(form.image_url)!} alt="Product photo preview" /> : <span className="muted">No photo yet</span>}
        </div>
        <div className="photo-actions">
          <label className="btn btn-small btn-quiet file-btn">
            {uploading ? "Uploading…" : form.image_url ? "Change photo" : "Upload photo"}
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => pickPhoto(e.target.files?.[0])} disabled={uploading} />
          </label>
          {form.image_url && <button type="button" className="link-button" onClick={() => setForm({ ...form, image_url: null })}>Remove photo</button>}
          <span className="hint">JPG, PNG or WebP, up to 2 MB. A square photo looks best.</span>
        </div>
      </div>

      <label className="span-2">Product name<input required minLength={3} maxLength={200} value={form.name} onChange={set("name")} /></label>
      <label>Brand<input maxLength={100} value={form.brand} onChange={set("brand")} /></label>
      <label>
        Category
        <select required value={form.category_id} onChange={set("category_id")}>
          <option value="">Choose…</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </label>
      <label>Selling price (₹)<input required type="number" min={1} step="0.01" value={form.price} onChange={set("price")} /></label>
      <label>
        MRP (₹)
        <input required type="number" min={1} step="0.01" value={form.mrp} onChange={set("mrp")} />
        <span className="hint">{discount > 0 ? `Shoppers see ${discount}% off` : "Set MRP above the price to show a discount"}</span>
      </label>
      <label>Units in stock<input required type="number" min={0} value={form.stock} onChange={set("stock")} /></label>
      <label>
        Warn me when stock falls to
        <input required type="number" min={0} value={form.low_stock_threshold} onChange={set("low_stock_threshold")} />
      </label>
      <label className="span-2">Description<textarea rows={4} maxLength={5000} value={form.description} onChange={set("description")} /></label>

      {error && <p className="error span-2" role="alert">{error}</p>}
      <div className="actions span-2">
        <button className="btn" disabled={busy || uploading}>{busy ? "Saving…" : listing ? "Save changes" : "Submit for review"}</button>
        <button type="button" className="link-button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}
