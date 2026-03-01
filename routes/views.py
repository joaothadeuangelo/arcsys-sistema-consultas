from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from database import is_manutencao

router = APIRouter()

# Aponta para a pasta onde criamos nossos HTMLs
templates = Jinja2Templates(directory="templates")

@router.get("/")
async def render_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "manutencao": is_manutencao()
    })

@router.get("/placa")
async def render_placa(request: Request):
    return templates.TemplateResponse("modulo_placa.html", {
        "request": request, 
        "manutencao": is_manutencao()
    })

@router.get("/cnh")
async def render_cnh(request: Request):
    return templates.TemplateResponse("modulo_cnh.html", {
        "request": request, 
        "manutencao": is_manutencao()
    })