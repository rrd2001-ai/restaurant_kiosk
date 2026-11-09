import json
from app.config import MENU_PATH

def load_menu():
    if not MENU_PATH.exists():
        raise RuntimeError(f"Menu file not found: {MENU_PATH}")
    data = json.loads(MENU_PATH.read_text(encoding="utf-8"))
    items = data.get("items")
    if not isinstance(items, list) or not items:
        raise RuntimeError("menu.json must contain a non-empty 'items' array")
    ids = set()
    for item in items:
        if not all(k in item for k in ("id", "name", "price")):
            raise RuntimeError("Each menu item needs id, name and price")
        if item["id"] in ids or not isinstance(item["price"], int) or item["price"] < 0:
            raise RuntimeError("Menu IDs must be unique and prices non-negative integers")
        ids.add(item["id"])
    return data
