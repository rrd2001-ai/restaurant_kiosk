from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.config import BASE_DIR
from app.database import init_db
from app.menu import load_menu
from app.api.routes import router, configure

menu_data=load_menu()
configure(menu_data)
init_db()
app=FastAPI(title="Namma Veedu AI Restaurant Kiosk",version="2.0.0")
app.mount("/static",StaticFiles(directory=str(BASE_DIR/"app"/"static")),name="static")
templates=Jinja2Templates(directory=str(BASE_DIR/"app"/"templates"))
app.include_router(router)

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request,"index.html",{"restaurant":menu_data.get("restaurant_name","Namma Veedu")})

@app.get("/health")
def health(): return {"status":"ok","service":"restaurant-kiosk"}
