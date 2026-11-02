import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type CartSummary } from "./api";
import { useAuth } from "./auth";

interface CartState {
  carts: CartSummary[];
  active: CartSummary | null;
  refresh: () => Promise<void>;
}

const CartContext = createContext<CartState>({ carts: [], active: null, refresh: async () => {} });

// Keeps the list of the buyer's carts in one place, so the nav badge and the
// "Add to cart" picker stay in sync after any change.
export function CartProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [carts, setCarts] = useState<CartSummary[]>([]);

  const refresh = useCallback(async () => {
    if (user?.role !== "buyer") { setCarts([]); return; }
    try { setCarts(await api<CartSummary[]>("/api/cart/carts")); } catch { /* keep the old list */ }
  }, [user]);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <CartContext.Provider value={{ carts, active: carts.find((c) => c.is_active) ?? null, refresh }}>
      {children}
    </CartContext.Provider>
  );
}

export const useCarts = () => useContext(CartContext);
