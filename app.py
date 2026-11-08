import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Import from our new local modules
from database import init_customer_db, get_customer, save_customer
from matcher import match_item

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Initialize database on startup
init_customer_db()

# Load menu metadata
with open("menu.json", "r") as f:
    menu_data = json.load(f)

class OrderItem(BaseModel):
    name: str
    quantity: int
    price: float

class OrderRequest(BaseModel):
    items: List[OrderItem]

class CustomerLookup(BaseModel):
    phone: str

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "restaurant": menu_data["restaurant_name"], 
        "menu": menu_data["items"]
    })

@app.post("/api/voice-order")
async def voice_order(data: dict):
    spoken = data.get("text", "")
    item, score = match_item(spoken)
    if item:
        return {"success": True, "item": item, "score": score}
    return {"success": False, "spoken": spoken, "message": "Could not match item"}

@app.post("/api/customer/lookup")
async def lookup_customer(data: CustomerLookup):
    row = get_customer(data.phone)
    if row:
        return {"found": True, "name": row[0], "last_order": row[1], "visit_count": row[2]}
    return {"found": False}

@app.post("/api/customer/save")
async def save_customer_order(data: dict):
    save_customer(data.get("phone"), data.get("name", "Valued Customer"), data.get("summary"))
    return {"success": True}

@app.post("/api/checkout")
async def checkout(order: OrderRequest):
    receipt_filename = "receipt.pdf"
    c = canvas.Canvas(receipt_filename, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, menu_data["restaurant_name"])
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, "Customer Order Receipt")
    c.line(50, height - 80, 550, height - 80)
    
    y = height - 100
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Item")
    c.drawString(300, y, "Qty")
    c.drawString(400, y, "Price (₹)")
    
    y -= 20
    c.setFont("Helvetica", 10)
    total = 0
    for item in order.items:
        item_total = item.price * item.quantity
        total += item_total
        c.drawString(50, y, item.name)
        c.drawString(300, y, str(item.quantity))
        c.drawString(400, y, f"₹{item_total}")
        y -= 20
        
    c.line(50, y - 5, 550, y - 5)
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Total Amount: ₹{total}")
    c.save()
    
    return {"success": True, "total": total, "receipt_url": "/api/download-receipt"}

@app.get("/api/download-receipt")
async def download_receipt():
    return FileResponse("receipt.pdf", media_type="application/pdf", filename="receipt.pdf")