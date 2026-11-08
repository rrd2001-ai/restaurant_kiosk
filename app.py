import json
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from rapidfuzz import process, fuzz

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Load menu
with open("menu.json", "r") as f:
    menu_data = json.load(f)

menu_items = {item["name"]: item for item in menu_data["items"]}
menu_names = list(menu_items.keys())
STOP_WORDS = {"i", "want", "give", "me", "please", "would", "like", "a", "an", "the", "can", "you", "get"}

def clean_spoken_text(text):
    words = text.lower().split()
    return " ".join([w for w in words if w not in STOP_WORDS])

class OrderItem(BaseModel):
    name: str
    quantity: int
    price: float

class OrderRequest(BaseModel):
    items: List[OrderItem]

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "restaurant": menu_data["restaurant_name"], 
        "menu": menu_data["items"]
    })
    
@app.post("/api/match-voice")
async def match_voice(data: dict):
    spoken = data.get("text", "")
    cleaned = clean_spoken_text(spoken)
    query = cleaned if cleaned else spoken
    
    best_match, score, _ = process.extractOne(query, menu_names, scorer=fuzz.WRatio)
    if score >= 65:
        item = menu_items[best_match]
        return {"success": True, "item": item, "score": score}
    return {"success": False, "message": "Item not recognized"}

@app.post("/api/checkout")
async def checkout(order: OrderRequest):
    receipt_filename = "receipt.pdf"
    
    # Generate PDF Receipt using ReportLab
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