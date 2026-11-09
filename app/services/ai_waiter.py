"""Drop-in Rasa NLU adapter; preserves the existing ask_waiter() interface."""
from __future__ import annotations
import logging, os, re
from typing import Any
import httpx

logger = logging.getLogger(__name__)
RASA_NLU_URL = os.getenv("RASA_NLU_URL", "http://127.0.0.1:5005/model/parse")
RASA_TIMEOUT = float(os.getenv("RASA_TIMEOUT", "8"))
NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20}
ALIASES = {"coke": ("coke", "cokes", "coca cola"), "filter coffee": ("filter coffee",), "chicken burger": ("chicken burger",), "paneer burger": ("paneer burger",), "margherita pizza": ("margherita", "margherita pizza"), "pepperoni pizza": ("pepperoni", "pepperoni pizza"), "masala dosa": ("masala dosa", "masala dosai")}

def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.casefold()).split())

def _result(action="answer", message="How else can I help you?", add=None, remove=None):
    return {"action": action, "message": message, "items_to_add": add or [], "items_to_remove": remove or []}

def _parse(text: str) -> dict[str, Any]:
    response = httpx.post(RASA_NLU_URL, json={"text": text}, timeout=RASA_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Invalid Rasa response")
    return data

def _menu_aliases(item: dict) -> set[str]:
    name = _norm(str(item.get("name", "")))
    return {_norm(alias) for alias in (*ALIASES.get(name, ()), name) if _norm(alias)}


def _find_items(text: str, menu: list[dict]) -> list[tuple[dict, int]]:
    """Find every menu item mentioned and attach its immediately preceding quantity.

    Matching is performed against the live menu, never against model-generated IDs.
    The longest alias wins when aliases overlap (for example, a full pizza name).
    """
    normalized = _norm(text)
    matches: list[tuple[int, int, dict]] = []
    for item in menu:
        for alias in _menu_aliases(item):
            for match in re.finditer(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized):
                matches.append((match.start(), match.end(), item))

    # Resolve overlaps by preferring the longest match at a given position.
    matches.sort(key=lambda value: (value[0], -(value[1] - value[0])))
    selected: list[tuple[int, int, dict]] = []
    for candidate in matches:
        start, end, item = candidate
        if selected and start < selected[-1][1]:
            continue
        selected.append(candidate)

    found: list[tuple[dict, int]] = []
    previous_end = 0
    quantity_pattern = re.compile(
        r"\b(\d{1,2}|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")\b"
    )
    for start, end, item in selected:
        prefix = normalized[previous_end:start]
        quantities = list(quantity_pattern.finditer(prefix))
        quantity = 1
        if quantities:
            raw = quantities[-1].group(1)
            quantity = int(raw) if raw.isdigit() else NUMBER_WORDS[raw]
            quantity = max(1, min(99, quantity))
        found.append((item, quantity))
        previous_end = end
    return found


def _quantity(text: str, entities: list[dict]) -> int:
    for entity in entities:
        if entity.get("entity") == "quantity":
            value = str(entity.get("value", "")).casefold()
            if value.isdigit(): return max(1, min(99, int(value)))
            if value in NUMBER_WORDS: return NUMBER_WORDS[value]
    match = re.search(r"\b(\d{1,2})\b", text)
    if match: return max(1, min(99, int(match.group(1))))
    return next((NUMBER_WORDS[w] for w in _norm(text).split() if w in NUMBER_WORDS), 1)

def _menu_reply(menu: list[dict]) -> str:
    groups = {}
    for item in menu:
        category = str(item.get("category") or "Other")
        price = item.get("price")
        label = str(item.get("name", "Item")) + (f" (Rs. {price})" if price is not None else "")
        groups.setdefault(category, []).append(label)
    if not groups: return "Our menu is unavailable right now. Please ask a team member for help."
    return "Here is our menu:\n" + "\n".join(f"{k}: {', '.join(v)}" for k, v in groups.items()) + "\nWhat would you like?"

def ask_waiter(user_text, menu, cart, history, checkout_pending, restaurant):
    """Rasa classifies intent; Python owns dialogue state and all order mutations."""
    del history  # retained for compatibility with the existing route signature
    text = user_text.strip()
    try:
        parsed = _parse(text)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("Rasa NLU unavailable: %s", exc)
        return _result(message="I can't understand messages right now. Please try again or use the menu buttons.")
    intent = str((parsed.get("intent") or {}).get("name") or "nlu_fallback")
    confidence = float((parsed.get("intent") or {}).get("confidence") or 0)
    entities = parsed.get("entities") or []
    normalized = _norm(text)

    # Checkout is intentionally conservative. The FastAPI route should remain
    # the final authority and should resolve pending confirmation before NLU.
    if checkout_pending:
        if intent == "affirm" and normalized in {"yes", "yes please", "yeah", "yep", "yup", "sure", "confirm", "confirm my order", "go ahead"}:
            return _result("confirm_checkout", "Thank you. Your order is confirmed.")
        if intent == "deny" and normalized in {"no", "no thanks", "no thank you", "not now", "cancel"}:
            return _result("cancel_checkout", "No problem. We can continue ordering.")
        return _result("ask_checkout_confirmation", "Please say yes to confirm your order, or no to continue ordering.")

    if intent == "greet": return _result(message=f"Hello! Welcome to {restaurant}. How can I help you today?")
    if intent == "thank": return _result(message="You're very welcome! Would you like anything else?")
    if intent == "goodbye": return _result(message="Thank you for visiting! Have a lovely day.")
    if intent in {"ask_menu", "menu_query"}: return _result(message=_menu_reply(menu))
    if intent in {"show_cart", "ask_order_status"}:
        by_id = {str(x.get("id")): x for x in menu}
        lines = [f"{x.get('quantity', 1)} × {by_id[str(x.get('id'))].get('name')}" for x in cart if str(x.get('id')) in by_id]
        return _result(message="Your current order: " + (", ".join(lines) if lines else "Your cart is empty."))
    if intent in {"ask_checkout_confirmation", "checkout"}:
        return _result("ask_checkout_confirmation", "Would you like me to confirm your order and prepare your receipt?")
    if intent == "affirm": return _result(message="Of course. What else would you like to order?")
    if intent == "deny": return _result(message="No problem. Is there anything else I can help you with?")
    if intent in {"recommend", "ask_recommendation"}:
        choices = ", ".join(str(x.get("name")) for x in menu[:5])
        return _result(message=f"Here are a few options from our menu: {choices}. What sounds good?")

    found_items = _find_items(text, menu)
    is_remove = intent in {"remove_items", "remove_item"} or any(p in normalized for p in ("remove ", "delete ", "take off ", "take out ", "cancel the ", "don't want ", "do not want "))
    is_add = intent in {"add_items", "add_item", "order_item"} or any(p in normalized for p in ("i want ", "i would like ", "can i get ", "please add ", "add ", "get me ", "ill have ", "i'll have ", "give me ", "i need "))
    # A quantity immediately before a menu item is also a natural order request:
    # e.g. "three Coke, two masala dosa and four chicken burgers".
    quantity_words = [word for word in NUMBER_WORDS if word not in {"a", "an"}]
    has_quantity = bool(re.search(r"\b(\d{1,2}|" + "|".join(quantity_words) + r")\b", normalized))
    if found_items and (is_add or (not is_remove and has_quantity)):
        requested = []
        totals: dict[str, dict] = {}
        for found_item, qty in found_items:
            item_id = str(found_item["id"])
            if item_id not in totals:
                totals[item_id] = {"id": found_item["id"], "quantity": 0, "name": found_item["name"]}
            totals[item_id]["quantity"] = min(99, totals[item_id]["quantity"] + qty)
        requested = [{"id": value["id"], "quantity": value["quantity"]} for value in totals.values()]
        summary = ", ".join(f"{value['quantity']} × {value['name']}" for value in totals.values())
        if is_remove:
            return _result("remove_items", f"I'll remove {summary} from your order.", remove=requested)
        return _result("add_items", f"I'll add {summary} to your order.", add=requested)
    if found_items and is_remove:
        requested = [{"id": item["id"], "quantity": qty} for item, qty in found_items]
        summary = ", ".join(f"{qty} × {item['name']}" for item, qty in found_items)
        return _result("remove_items", f"I'll remove {summary} from your order.", remove=requested)
    if intent in {"add_items", "add_item", "order_item", "remove_items", "remove_item"}:
        return _result("ask_clarification", "Which item would you like? You can ask to see our menu first.")
    if found_items:
        names = ", ".join(item["name"] for item, _ in found_items)
        return _result("ask_clarification", f"Would you like me to add {names} to your order?")
    if confidence < 0.45 or intent == "nlu_fallback":
        return _result("ask_clarification", "I'm not sure I understood. You can ask to see the menu, add or remove an item, or check your cart.")
    if intent == "ask_price":
        return _result(message="Which menu item would you like the price for?")
    if intent == "ask_ingredients":
        return _result(message="Which dish would you like ingredient information for?")
    return _result(message="How else can I help you with your order?")
