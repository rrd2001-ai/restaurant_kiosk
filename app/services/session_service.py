import json, uuid
from fastapi import HTTPException
from app.database import get_db

def create_session():
    sid = str(uuid.uuid4())
    with get_db() as db:
        db.execute("INSERT INTO sessions(id) VALUES (?)", (sid,))
    return sid

def get_session(sid):
    with get_db() as db:
        row = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise HTTPException(404, "Session not found. Please start a new order.")
    data = dict(row)
    data["cart"] = json.loads(data.pop("cart_json"))
    data["history"] = json.loads(data.pop("history_json"))
    data["checkout_pending"] = bool(data["checkout_pending"])
    return data

def save_session(session):
    with get_db() as db:
        db.execute("""UPDATE sessions SET customer_name=?, customer_phone=?, cart_json=?,
          history_json=?, checkout_pending=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?""",
          (session["customer_name"], session.get("customer_phone"), json.dumps(session["cart"]),
           json.dumps(session["history"][-30:]), int(session["checkout_pending"]), session["status"], session["id"]))
