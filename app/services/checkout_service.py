import secrets
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.config import RECEIPTS_DIR
from app.database import get_db
from app.services.cart_service import cart_details

def create_receipt(session, menu_by_id, restaurant):
    details = cart_details(session["cart"], menu_by_id)
    if not details["items"]: raise ValueError("Your cart is empty.")
    order_id = secrets.token_hex(8)
    filename = f"receipt_{order_id}.pdf"
    path = RECEIPTS_DIR / filename
    pdf = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    pdf.setTitle(f"{restaurant} receipt")
    pdf.setFont("Helvetica-Bold", 18); pdf.drawString(48, height-48, restaurant)
    pdf.setFont("Helvetica", 10); pdf.drawString(48, height-70, f"Order receipt: {order_id}")
    pdf.drawString(48, height-85, f"Customer: {session['customer_name']}")
    y = height-125
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(48,y,"Item"); pdf.drawString(340,y,"Qty"); pdf.drawString(420,y,"Amount")
    y -= 22; pdf.setFont("Helvetica",10)
    for item in details["items"]:
        if y < 65: pdf.showPage(); y = height-55; pdf.setFont("Helvetica",10)
        pdf.drawString(48,y,item["name"][:42]); pdf.drawString(340,y,str(item["quantity"])); pdf.drawString(420,y,f"Rs. {item['subtotal']}"); y -= 19
    y -= 12; pdf.setFont("Helvetica-Bold",13); pdf.drawString(340,y,f"Total: Rs. {details['total']}")
    pdf.save()
    with get_db() as db:
        db.execute("INSERT INTO orders(id,session_id,customer_name,items_json,total,receipt_filename) VALUES(?,?,?,?,?,?)",
                   (order_id,session["id"],session["customer_name"],__import__('json').dumps(details["items"]),details["total"],filename))
        if session.get("customer_phone"):
            db.execute("""INSERT INTO customers(phone,name,last_order,visit_count) VALUES(?,?,?,1)
              ON CONFLICT(phone) DO UPDATE SET name=excluded.name,last_order=excluded.last_order,
              visit_count=customers.visit_count+1,updated_at=CURRENT_TIMESTAMP""",
              (session["customer_phone"],session["customer_name"],", ".join(i["name"] for i in details["items"])))
    return {"receipt_id":order_id,"receipt_url":f"/api/receipts/{order_id}","total":details["total"]}
