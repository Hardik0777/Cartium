"""Store FAQs and policies the assistant can quote. Every rule here matches how the app actually
behaves, so the assistant never invents a policy. If you change a rule in the code, change it here:
  delivery fee and free-delivery limit -> core/config.py (shipping_fee, free_shipping_over)
  15-minute payment hold               -> core/config.py (payment_window_minutes)
  max carts                            -> services/carts.py (MAX_CARTS)
  cancellation and refund rules        -> routers/seller.py, routers/admin.py"""

FAQS = [
    ("How much is delivery?",
     "Delivery is free on orders of ₹499 or more. Below that, delivery costs ₹40."),
    ("Can I keep more than one cart?",
     "Yes. You can have up to 10 named carts, like 'Groceries' or 'Diwali gifts', and check out each one "
     "separately. Pick which cart new items go into on the product page or the Carts page."),
    ("Which payment methods do you accept?",
     "Payments go through Razorpay: UPI, cards, netbanking and wallets. Cartium never sees or stores your card details."),
    ("How long are items held while I pay?",
     "When you start checkout, the items are reserved for 15 minutes. If you close the payment window, "
     "they're released straight away."),
    ("How do I track my order?",
     "Open Orders and pick an order. Each item shows Placed, Packed, Shipped or Delivered, updated by the seller. "
     "You can also ask me 'where is my order?'"),
    ("Can I buy the same things again?",
     "Yes. Open a past order and press 'Buy these again' to put the available items back in your cart."),
    ("How do I report a problem with an order?",
     "Open the order and press 'Report a problem'. Cartium support replies on the same page."),
    ("How do I become a seller?",
     "Sign up and choose 'Sell'. An admin reviews new sellers; once approved you can list products, "
     "and each new product is also reviewed before it appears in the store."),
]

POLICIES = [
    ("Cancellations",
     "A seller can cancel an item until it has shipped. Once an item is shipped it can't be cancelled. "
     "If a seller cancels an item you paid for, a refund for that item is created automatically."),
    ("Refunds",
     "Refunds are sent by Cartium's team through Razorpay to your original payment method. "
     "Each refund is sent once; the amount is exactly what you paid for the cancelled items."),
    ("Payment safety",
     "Every payment is confirmed by checking Razorpay's signature on the server. If a payment arrives after "
     "the 15-minute hold has expired, the full amount is refunded."),
    ("Product listings",
     "Only listings approved by an admin, from approved sellers, appear in the store. Prices and stock "
     "shown are always the current ones."),
    ("Reviews",
     "Only shoppers can review products, one review per product, which they can edit or delete. Sellers can "
     "reply publicly. Reviews show the reviewer's first name only."),
    ("Account security",
     "Passwords are stored hashed, never in plain text. You can sign in with Google. Logging out signs you "
     "out on every device."),
]
