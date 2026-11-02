import { Link } from "react-router-dom";
import { formatINR, type ProductCard } from "../api";
import ProductImage from "./ProductImage";
import Stars from "./Stars";

export default function ProductTile({ product }: { product: ProductCard }) {
  const out = product.stock_label === "out_of_stock";
  return (
    <Link to={`/products/${product.id}`} className={out ? "tile tile-out" : "tile"}>
      <ProductImage product={product} />
      <div className="tile-body">
        <span className="tile-brand">{product.brand}</span>
        <span className="tile-name">{product.name}</span>
        <Stars value={product.rating_avg} count={product.rating_count} />
        <span className="price-row">
          <strong>{formatINR(product.price)}</strong>
          {product.discount_pct > 0 && (
            <>
              <s className="muted">{formatINR(product.mrp)}</s>
              <span className="off">{product.discount_pct}% off</span>
            </>
          )}
        </span>
        {out && <span className="stock stock-out">Out of stock</span>}
        {product.stock_label === "low" && <span className="stock stock-low">Only {product.stock} left</span>}
      </div>
    </Link>
  );
}
