from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from database import is_manutencao, is_manutencao_modulo

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ==========================================
# ROTA VISUAL: DASHBOARD
# ==========================================
@router.get("/")
async def render_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "manutencao": is_manutencao(),
        "manutencao_placa": is_manutencao_modulo('placa'),
        "manutencao_cnh": is_manutencao_modulo('cnh'),
        "manutencao_cpf": is_manutencao_modulo('cpf')
    })

# ==========================================
# ROTA VISUAL: MÓDULO PLACA
# ==========================================
@router.get("/placa")
async def render_placa(request: Request):
    # Se o sistema global ou o módulo placa estiver off, chuta pro início
    if is_manutencao() or is_manutencao_modulo('placa'):
        return RedirectResponse(url="/", status_code=303)
        
    return templates.TemplateResponse("modulo_placa.html", {
        "request": request, 
        "manutencao": is_manutencao()
    })

# ==========================================
# ROTA VISUAL: MÓDULO CNH
# ==========================================
@router.get("/cnh")
async def render_cnh(request: Request):
    if is_manutencao() or is_manutencao_modulo('cnh'):
        return RedirectResponse(url="/", status_code=303)
        
    return templates.TemplateResponse("modulo_cnh.html", {
        "request": request, 
        "manutencao": is_manutencao()
    })
    
# ==========================================
# ROTA VISUAL: MÓDULO DE DADOS (CPF / SISREG)
# ==========================================
@router.get("/cpf")
async def render_cpf(request: Request):
    if is_manutencao() or is_manutencao_modulo('cpf'):
        return RedirectResponse(url="/", status_code=303)
        
    return templates.TemplateResponse("modulo_cpf.html", {
        "request": request, 
        "manutencao": is_manutencao()
    })
    
# ==========================================
# ROTA VISUAL: SEPARADOR DE CPF (FERRAMENTA 100% FRONT-END)
# ==========================================
@router.get("/separador", response_class=HTMLResponse)
async def render_separador(request: Request):
    # O separador não tem módulo no DB, mas respeita a manutenção global
    if is_manutencao():
        return RedirectResponse(url="/", status_code=303)
        
    return templates.TemplateResponse("modulo_separador.html", {
        "request": request,
        "manutencao": is_manutencao()
    })