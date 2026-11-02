// Loads Razorpay Checkout on demand and wraps it in a promise.
// Docs: https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/
import type { Checkout } from "./api";

export interface RazorpayResult {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

declare global {
  interface Window { Razorpay?: new (options: Record<string, unknown>) => { open: () => void; on: (e: string, cb: (r: unknown) => void) => void } }
}

const SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

function loadScript(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = SCRIPT;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Couldn't load Razorpay. Check your internet connection."));
    document.body.appendChild(s);
  });
}

export class PaymentClosed extends Error {}

export async function pay(checkout: Checkout): Promise<RazorpayResult> {
  await loadScript();
  return new Promise((resolve, reject) => {
    const rzp = new window.Razorpay!({
      key: checkout.key_id,
      amount: checkout.amount,
      currency: checkout.currency,
      order_id: checkout.razorpay_order_id,
      name: "Cartium",
      description: `Order #${checkout.order_id}`,
      prefill: { name: checkout.name, email: checkout.email, contact: checkout.contact },
      theme: { color: "#0e4f5c" },
      handler: (res: RazorpayResult) => resolve(res),
      modal: { ondismiss: () => reject(new PaymentClosed("Payment window closed")) },
    });
    rzp.on("payment.failed", (r) => {
      const desc = (r as { error?: { description?: string } }).error?.description;
      reject(new Error(desc ? `Payment failed: ${desc}` : "Payment failed. No money was taken; try again."));
    });
    rzp.open();
  });
}
