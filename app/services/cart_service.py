from fastapi import HTTPException

def cart_details(cart, menu_by_id):
    items, total = [], 0
    for item_id, quantity in cart.items():
        item = menu_by_id.get(item_id)
        if item and quantity > 0:
            subtotal = item["price"] * quantity
            total += subtotal
            items.append({"id": item_id, "name": item["name"], "price": item["price"], "quantity": quantity, "subtotal": subtotal})
    return {"items": items, "total": total, "count": sum(x["quantity"] for x in items)}

def add_items(cart, requested, menu_by_id):
    for entry in requested:
        item_id, qty = entry["id"], entry["quantity"]
        if item_id not in menu_by_id or not isinstance(qty, int) or isinstance(qty, bool) or not 1 <= qty <= 99:
            raise HTTPException(400, "Invalid menu item or quantity.")
        if cart.get(item_id, 0) + qty > 99:
            raise HTTPException(400, "Maximum quantity per item is 99.")
        cart[item_id] = cart.get(item_id, 0) + qty

def remove_items(cart, requested):
    for entry in requested:
        item_id, qty = entry["id"], entry["quantity"]
        remaining = max(0, cart.get(item_id, 0) - qty)
        if remaining: cart[item_id] = remaining
        else: cart.pop(item_id, None)
