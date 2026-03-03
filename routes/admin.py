import os
import sqlite3
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import DB_PATH, toggle_manutencao, toggle_manutencao_modulo, get_status_todos_modulos

router = APIRouter()
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'mudar_isso_depois')

# Configurando o renderizador de HTML
templates = Jinja2Templates(directory="templates")

# ==========================================
# ROTA DE AÇÃO (LIGAR/DESLIGAR)
# ==========================================
@router.get("/admin/toggle")
async def alternar_status(token: str, modulo: str = None):
    if token != ADMIN_TOKEN: return HTMLResponse("<h1>Acesso Negado</h1>", status_code=403)
    
    # Se recebeu um módulo específico, desliga só ele. Se não, desliga TUDO.
    if modulo in ['placa', 'cnh', 'cpf']:
        toggle_manutencao_modulo(modulo)
    else:
        toggle_manutencao()
        
    return RedirectResponse(url=f"/admin/lista?token={token}")

# ==========================================
# ROTA VISUAL: DASHBOARD DE ADMINISTRAÇÃO
# ==========================================
@router.get("/admin/lista", response_class=HTMLResponse)
async def ver_historico(request: Request, token: str):
    if token != ADMIN_TOKEN: return HTMLResponse("<h1>Acesso Negado</h1>", status_code=403)

    # 1. Puxa as consultas do banco
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT placa, dados, data_consulta FROM registro_placas ORDER BY data_consulta DESC LIMIT 100')
    rows = cursor.fetchall()
    conn.close()

    # 2. Puxa o status de todos os módulos
    status_todos = get_status_todos_modulos()
    
    # 3. Envia os dados mastigados para o HTML
    contexto = {
        "request": request,
        "token": token,
        "rows": rows,
        "status_global": status_todos.get('manutencao', False),
        "status_placa": status_todos.get('manutencao_placa', False),
        "status_cnh": status_todos.get('manutencao_cnh', False),
        "status_cpf": status_todos.get('manutencao_cpf', False)
    }

    return templates.TemplateResponse("admin.html", contexto)