import json
import subprocess
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from database import init_customer_db, get_customer, save_customer
from nlu_engine import process_voice_command, process_name_command

app = FastAPI()
templates = Jinja2Templates(directory="templates")

init_customer_db()

with open("menu.json", "r") as f:
    menu_data = json.load(f)

menu_items = {item["name"]: item for item in menu_data["items"]}

def speak_response(text):
    subprocess.Popen(["say", "-v", "Rishi", text])

class OrderItem(BaseModel):
    name: str
    quantity: int
    price: float

class OrderRequest(BaseModel):
    items: List[OrderItem]

class NameRequest(BaseModel):
    name: str

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    greeting = f"Welcome to {menu_data['restaurant_name']}. May I have your name please?"
    speak_response(greeting)
    return templates.TemplateResponse(request, "index.html", {
        "restaurant": menu_data["restaurant_name"],
        "greeting": greeting
    })

@app.post("/api/greet-customer")
async def greet_customer(data: NameRequest):
    spoken_input = data.name.strip()
    nlu_res = process_name_command(spoken_input)
    clean_name = nlu_res.get("name", spoken_input).strip().title()
    
    reply = f"Hi {clean_name}! Nice to meet you. What would you like to order today?"
    speak_response(reply)
    return {"success": True, "name": clean_name, "reply": reply}

@app.get("/menu", response_class=HTMLResponse)
async def menu_screen(request: Request, name: str = "Guest"):
    return templates.TemplateResponse(request, "menu.html", {
        "restaurant": menu_data["restaurant_name"],
        "menu": menu_data["items"],
        "customer_name": name
    })

@app.post("/api/voice-order")
async def voice_order(data: dict):
    spoken = data.get("text", "")
    nlu_result = process_voice_command(spoken)
    
    if nlu_result.get("intent") == "checkout":
        reply_message = "Certainly! Let's get your receipt printed."
        speak_response(reply_message)
        return {
            "success": True,
            "intent": "checkout",
            "items": [],
            "spoken": spoken,
            "reply": reply_message
        }
    
    matched_items = []
    for parsed in nlu_result.get("items", []):
        item_name = parsed.get("name")
        if item_name in menu_items:
            item_data = menu_items[item_name].copy()
            item_data["quantity"] = parsed.get("quantity", 1)
            matched_items.append(item_data)
            
    reply_message = nlu_result.get("waiter_reply", "Got it! Anything else?")
    speak_response(reply_message)
    
    return {
        "success": len(matched_items) > 0,
        "intent": "order",
        "items": matched_items,
        "spoken": spoken,
        "reply": reply_message
    }

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
    
    speak_response(f"Order confirmed! Your total is {total} rupees. Your receipt is printing.")
    return {"success": True, "total": total, "receipt_url": "/api/download-receipt"}

@app.get("/api/download-receipt")
async def download_receipt():
    return FileResponse("receipt.pdf", media_type="application/pdf", filename="receipt.pdf")