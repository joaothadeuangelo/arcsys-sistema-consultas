from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from database import is_manutencao, is_manutencao_modulo, registrar_evento_telemetria_background

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def obter_ip_telemetria(request: Request) -> str:
    ip_cloudflare = request.headers.get("CF-Connecting-IP")
    if ip_cloudflare:
        return ip_cloudflare

    ip_proxy = request.headers.get("X-Forwarded-For")
    if ip_proxy:
        return ip_proxy.split(",")[0].strip()

    return request.client.host if request.client else "anonimo"

# ==========================================
# ROTA VISUAL: DASHBOARD
# ==========================================
@router.get("/")
async def render_dashboard(request: Request):
    registrar_evento_telemetria_background("page_view", "home", obter_ip_telemetria(request))
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "manutencao": is_manutencao(),
        "manutencao_placa": is_manutencao_modulo('placa'),
        "manutencao_cnh": is_manutencao_modulo('cnh'),
        "manutencao_cpf": is_manutencao_modulo('cpf'),
        "manutencao_nome": is_manutencao_modulo('nome'),
        # 🎯 ADICIONADO: Envia o status do Comparador para o Front-end
        "manutencao_comparador": is_manutencao_modulo('comparador')
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
# ROTA VISUAL: MÓDULO DE CONSULTA POR NOME
# ==========================================
@router.get("/nome")
async def render_nome(request: Request):
    if is_manutencao() or is_manutencao_modulo('nome'):
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("modulo_nome.html", {
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
    
# ==========================================
# ROTA VISUAL: SIMILAR FACE (COMPARADOR)
# ==========================================
@router.get("/comparador", response_class=HTMLResponse)
async def comparador_page(request: Request):
    # 🎯 TRAVA DE SEGURANÇA: Respeita a manutenção global E a manutenção individual do módulo
    if is_manutencao() or is_manutencao_modulo('comparador'):
        return RedirectResponse(url="/", status_code=303)
        
    return templates.TemplateResponse("modulo_comparador.html", {
        "request": request,
        "manutencao": is_manutencao()
    })