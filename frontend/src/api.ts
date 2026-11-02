// Small fetch wrapper: adds the JWT, turns API errors into readable messages.
export const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://127.0.0.1:8000";
const TOKEN_KEY = "cartium_token";

export const tokenStore = {
  get(): string | null {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set(token: string | null) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch { /* storage blocked: stay logged in for this tab only */ }
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function readableDetail(detail: unknown): string {
  // FastAPI validation errors arrive as a list of {loc, msg}.
  if (Array.isArray(detail)) {
    return detail.map((d) => String(d.msg).replace(/^Value error, /, "")).join(". ");
  }
  return typeof detail === "string" ? detail : "Something went wrong. Try again.";
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = tokenStore.get();
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new ApiError(0, "Can't reach the Cartium server. Check that the backend is running.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, readableDetail(data.detail));
  return data as T;
}

export type Role = "buyer" | "seller" | "admin";

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  seller_status: "pending" | "approved" | "rejected" | "suspended" | null;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}

// ---------------------------------------------------------------- catalog (Phase 2)
export interface Category { id: number; name: string; slug: string }

export interface ProductCard {
  id: number;
  name: string;
  brand: string;
  price: number;
  mrp: number;
  stock: number;
  image_url: string | null;
  rating_avg: number;
  rating_count: number;
  category: Category;
  seller: { id: number; name: string };
  discount_pct: number;
  stock_label: "in_stock" | "low" | "out_of_stock";
}

export interface ProductDetail extends ProductCard {
  description: string;
  in_wishlist: boolean;
}

export interface ProductPage { items: ProductCard[]; total: number; page: number; pages: number }

export interface Review {
  id: number;
  rating: number;
  body: string;
  author: string;
  is_mine: boolean;
  seller_response: string | null;
  created_at: string;
}

export interface ReviewSummary {
  average: number;
  count: number;
  distribution: Record<string, number>;
  reviews: Review[];
}

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
export const formatINR = (n: number) => inr.format(n);

// ---------------------------------------------------------------- carts and orders (Phase 3)
export interface CartSummary { id: number; name: string; is_active: boolean; item_count: number; subtotal: number }

export interface CartLine { id: number; product: ProductCard; quantity: number; line_total: number; problem: string | null }

export interface CartDetail extends CartSummary {
  lines: CartLine[];
  shipping_fee: number;
  total: number;
  can_checkout: boolean;
}

export interface Address {
  id: number;
  full_name: string;
  phone: string;
  line1: string;
  line2: string;
  city: string;
  state: string;
  pincode: string;
  is_default: boolean;
}

export interface Checkout {
  order_id: number;
  razorpay_order_id: string;
  amount: number;
  currency: string;
  key_id: string;
  name: string;
  email: string;
  contact: string;
}

export type ItemStatus = "placed" | "packed" | "shipped" | "delivered" | "cancelled";

export interface Order {
  id: number;
  cart_name: string;
  status: "pending_payment" | "paid" | "cancelled";
  progress: ItemStatus | "pending_payment";
  subtotal: number;
  shipping_fee: number;
  total: number;
  ship_name: string;
  ship_phone: string;
  ship_address: string;
  created_at: string;
  paid_at: string | null;
  items: {
    id: number; product_id: number | null; name: string; unit_price: number; quantity: number;
    status: ItemStatus; status_updated_at: string; seller_name: string;
  }[];
}

export const json = (body: unknown, method = "POST"): RequestInit => ({ method, body: JSON.stringify(body) });

// ---------------------------------------------------------------- seller (Phase 4)
/** Uploaded photos are served by the API, so relative paths need the API's address in front. */
export const mediaUrl = (url: string | null) => (url && url.startsWith("/") ? BASE + url : url);

export async function uploadPhoto(file: File): Promise<string> {
  const body = new FormData();
  body.append("file", file);
  const token = tokenStore.get();
  let res: Response;
  try {
    res = await fetch(BASE + "/api/seller/uploads", { method: "POST", body, headers: token ? { Authorization: `Bearer ${token}` } : {} });
  } catch {
    throw new ApiError(0, "Can't reach the Cartium server. Check that the backend is running.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, readableDetail(data.detail));
  return data.url as string;
}

export interface Listing {
  id: number;
  name: string;
  brand: string;
  description: string;
  category_id: number;
  category_name: string;
  category_slug: string;
  price: number;
  mrp: number;
  stock: number;
  low_stock_threshold: number;
  image_url: string | null;
  status: "pending" | "approved" | "rejected" | "removed";
  rating_avg: number;
  rating_count: number;
  units_sold: number;
  created_at: string;
}

export interface SellerOrderItem {
  id: number;
  order_id: number;
  product_id: number | null;
  name: string;
  quantity: number;
  unit_price: number;
  status: ItemStatus;
  status_updated_at: string;
  ordered_at: string;
  buyer_name: string;
  ship_name: string;
  ship_phone: string;
  ship_address: string;
  next_statuses: ItemStatus[];
}

export interface SellerDashboardData {
  revenue: number;
  orders: number;
  units_sold: number;
  to_ship: number;
  live_listings: number;
  pending_listings: number;
  average_rating: number | null;
  low_stock: Listing[];
  top_products: { id: number; name: string; units: number; revenue: number }[];
}

export interface SellerReview {
  id: number;
  product_id: number;
  product_name: string;
  rating: number;
  body: string;
  author: string;
  seller_response: string | null;
  created_at: string;
}
