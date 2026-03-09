import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# ==========================================
# 🚨 CORREÇÃO: IMPORTANDO A FILA DE CLIENTES
# ==========================================
from routes.api import fila_clientes  # <-- Puxando a variável de onde ela nasceu

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
    
    # 🎯 ADICIONADO O 'comparador' NA LISTA DE MÓDULOS PERMITIDOS
    if modulo in ['placa', 'cnh', 'cpf', 'comparador']:
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
        "status_cpf": status_todos.get('manutencao_cpf', False),
        # 🎯 ADICIONADO O STATUS DO COMPARADOR
        "status_comparador": status_todos.get('manutencao_comparador', False)
    }

    return templates.TemplateResponse("admin.html", contexto)


# ==========================================
# ROTA ADMIN: STATUS DAS CONTAS TELEGRAM
# ==========================================
@router.get("/api/admin/status_contas")
async def verificar_status_contas():
    status_lista = []
    clientes_temporarios = []
    
    # 1. Pega quantos clientes estão livres na fila agora
    quantidade = fila_clientes.qsize()
    
    if quantidade == 0:
        return {"sucesso": False, "erro": "Nenhuma conta na fila (ou todas estão em uso no exato momento)."}

    try:
        # 2. Retira todos da fila para testar
        for _ in range(quantidade):
            cliente = await fila_clientes.get()
            clientes_temporarios.append(cliente)

        # 3. Testa um por um
        for idx, cliente in enumerate(clientes_temporarios):
            nome_sessao = "Desconhecido"
            if hasattr(cliente, 'session') and hasattr(cliente.session, 'filename'):
                nome_sessao = os.path.basename(cliente.session.filename)

            if not cliente.is_connected():
                status_lista.append({
                    "id": idx + 1, "sessao": nome_sessao, 
                    "status": "Desconectada", "cor": "red", "icone": "❌"
                })
                continue

            try:
                me = await cliente.get_me()
                nome_conta = me.first_name if me else "Sem Nome"
                telefone = f"+{me.phone}" if me and me.phone else "Oculto"
                
                status_lista.append({
                    "id": idx + 1, "sessao": nome_sessao, "nome": nome_conta, "telefone": telefone,
                    "status": "Operante", "cor": "green", "icone": "✅"
                })
            except Exception as e:
                status_lista.append({
                    "id": idx + 1, "sessao": nome_sessao, 
                    "status": "Sessão Morta/Banida", "cor": "red", "icone": "💀", "detalhe": str(e)
                })

    finally:
        # 4. DEVOLVE TODO MUNDO PRA FILA
        for c in clientes_temporarios:
            await fila_clientes.put(c)

    return {"sucesso": True, "contas": status_lista}