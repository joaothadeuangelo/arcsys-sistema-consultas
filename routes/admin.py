import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Importando TODA a inteligência do nosso database.py (o Model)
from database import (
    toggle_manutencao, 
    toggle_manutencao_modulo, 
    get_status_todos_modulos, 
    contar_total_consultas, 
    obter_historico_paginado
)

router = APIRouter()
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'mudar_isso_depois')

# Configurando o renderizador de HTML
templates = Jinja2Templates(directory="templates")

# ==========================================
# ROTA DE AÇÃO (LIGAR/DESLIGAR)
# ==========================================
@router.get("/admin/toggle")
async def alternar_status(token: str, modulo: str = None):
    if token != ADMIN_TOKEN: 
        return HTMLResponse("<h1>Acesso Negado</h1>", status_code=403)
    
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
async def ver_historico(request: Request, token: str, pagina: int = 1):
    if token != ADMIN_TOKEN: 
        return HTMLResponse("<h1>Acesso Negado</h1>", status_code=403)

    # --- LÓGICA DE PAGINAÇÃO ---
    ITENS_POR_PAGINA = 50
    
    # Prevenção: Se alguém digitar ?pagina=-5 ou 0 na URL, forçamos para a página 1
    if pagina < 1:
        pagina = 1
        
    offset = (pagina - 1) * ITENS_POR_PAGINA

    # 1. Puxa o total e calcula a quantidade de páginas
    total_consultas = contar_total_consultas()
    
    if total_consultas == 0:
        total_paginas = 1
    else:
        total_paginas = (total_consultas // ITENS_POR_PAGINA) + (1 if total_consultas % ITENS_POR_PAGINA > 0 else 0)

    # 2. Puxa os dados EXATOS daquela página (sem sobrecarregar a memória)
    rows = obter_historico_paginado(ITENS_POR_PAGINA, offset)

    # 3. Puxa o status de todos os módulos
    status_todos = get_status_todos_modulos()
    
    # 4. Envia os dados mastigados para o HTML
    contexto = {
        "request": request,
        "token": token,
        "rows": rows,
        "pagina_atual": pagina,
        "total_paginas": total_paginas,
        "total_consultas": total_consultas,
        "status_global": status_todos.get('manutencao', False),
        "status_placa": status_todos.get('manutencao_placa', False),
        "status_cnh": status_todos.get('manutencao_cnh', False),
        "status_cpf": status_todos.get('manutencao_cpf', False)
    }

    return templates.TemplateResponse("admin.html", contexto)