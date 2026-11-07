"""Spots requests that need the shopper's own data or an action. Decided from the shopper's message
only (never from model output or product text), so a seller's description can't trigger an action."""
import re

ORDER_WORDS = re.compile(r"\b(where('?s| is)? my|track|order status|status of my|my orders?|delivery of my|when will .* arrive|has my .* shipped)\b", re.I)
ORDER_ID = re.compile(r"(?:order\s*#?|#)(\d{1,9})", re.I)
ADD_TO_CART = re.compile(r"\b(?:add|put)\s+(?:an?\s+|the\s+|some\s+|\d+\s+)?(.+?)\s+(?:to|in|into)\s+(?:my\s+)?(?:(.+?)\s+)?cart\b", re.I)


def order_intent(text: str) -> dict | None:
    if not ORDER_WORDS.search(text) and not ORDER_ID.search(text):
        return None
    m = ORDER_ID.search(text)
    return {"order_id": int(m.group(1)) if m else None}


def cart_intent(text: str) -> dict | None:
    m = ADD_TO_CART.search(text)
    if not m:
        return None
    product, cart = m.group(1).strip(" ."), (m.group(2) or "").strip(" .\"'“”")
    if cart.lower() in ("", "my", "the", "a"):
        cart = ""
    return {"product_query": product, "cart_name": cart or None}


# ---------------------------------------------------------------- price limits ("under 1000", "between 500 and 2k")
_NUM = r"(?:rs\.?|inr|₹)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k)?\b"
_BETWEEN = re.compile(r"\b(?:between|from)\s+" + _NUM + r"\s*(?:and|to|-)\s*" + _NUM, re.I)
_MAX = re.compile(r"(?:\b(?:under|below|less than|cheaper than|within|upto|up to|max(?:imum)?|not more than|no more than)|<=?)\s*" + _NUM, re.I)
_MIN = re.compile(r"(?:\b(?:over|above|more than|at least|min(?:imum)?|starting at)|>=?)\s*" + _NUM, re.I)


def _amount(num: str, k: str | None) -> float:
    value = float(num.replace(",", ""))
    return value * 1000 if k else value


def price_range(text: str) -> tuple[float | None, float | None]:
    """(min, max) in rupees from phrases like 'under 1000', 'above ₹500', 'between 1k and 3k'."""
    if m := _BETWEEN.search(text):
        a, b = _amount(m.group(1), m.group(2)), _amount(m.group(3), m.group(4))
        return min(a, b), max(a, b)
    low = _amount(*_MIN.search(text).groups()) if _MIN.search(text) else None
    high = _amount(*_MAX.search(text).groups()) if _MAX.search(text) else None
    return low, high
