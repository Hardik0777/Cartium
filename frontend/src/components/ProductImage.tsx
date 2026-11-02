import { mediaUrl, type ProductCard } from "../api";

// Until sellers upload photos (Phase 4), each product gets a designed tile in its category's colour.
const TINTS: Record<string, [string, string]> = {
  electronics: ["#dbe9ff", "#1d4ed8"],
  fashion: ["#fde4ec", "#a3245a"],
  "home-kitchen": ["#fdeccc", "#9a5b00"],
  books: ["#e7e2f8", "#5b3fa8"],
  beauty: ["#ffe2dc", "#b4432c"],
  "sports-fitness": ["#d9f2e4", "#1d7148"],
  groceries: ["#eef3d2", "#5c6b12"],
};

function initials(name: string) {
  return name.split(/[\s,]+/).filter((w) => /^[A-Za-z]/.test(w)).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

export default function ProductImage({ product, size = "card" }: { product: Pick<ProductCard, "name" | "image_url" | "category">; size?: "card" | "large" }) {
  if (product.image_url) {
    return <img className={`product-img product-img-${size}`} src={mediaUrl(product.image_url)!} alt={product.name} loading="lazy" />;
  }
  const [bg, fg] = TINTS[product.category.slug] ?? ["#e4ecee", "#0e4f5c"];
  return (
    <div className={`product-img product-img-${size} product-tile`} style={{ background: bg, color: fg }} role="img" aria-label={product.name}>
      <span>{initials(product.name)}</span>
    </div>
  );
}
