import os
import time
import sqlite3
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from fastapi.staticfiles import StaticFiles

# ==========================================
# CONFIGURAÇÕES GERAIS E CREDENCIAIS
# ==========================================
load_dotenv()

API_ID = int(os.getenv('API_ID', 0))  
API_HASH = os.getenv('API_HASH', '')
BOT_USERNAME = os.getenv('BOT_USERNAME', '')
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'mudar_isso_depois')
AMBIENTE = os.getenv("AMBIENTE", "producao")

# Coleta todas as strings de sessão
SESSOES_STRINGS = [
    value.strip() for key, value in os.environ.items() 
    if key.startswith('SESSAO_') and value.strip()
]

# ==========================================
# ESTADO DA APLICAÇÃO E RATE LIMIT
# ==========================================
app = FastAPI(title="ARCSYS - Central de Consultas")

# Servindo arquivos estáticos (CSS, JS, Imagens)
app.mount("/static", StaticFiles(directory="static"), name="static")

fila_clientes = asyncio.Queue()
cooldowns_por_ip = {}
TEMPO_COOLDOWN = 120 # Tempo de espera em segundos entre consultas

# ==========================================
# GUARDA DE TRÂNSITO (REDIRECIONAMENTO 301)
# ==========================================
@app.middleware("http")
async def redirecionar_dominio_antigo(request: Request, call_next):
    host_atual = request.headers.get("host", "")
    if "auto-bot-production-9044.up.railway.app" in host_atual:
        nova_url = f"https://placa.arcangelopainel.xyz{request.url.path}"
        if request.url.query:
            nova_url += f"?{request.url.query}"
        return RedirectResponse(url=nova_url, status_code=301)
    
    return await call_next(request)

# ==========================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# ==========================================
DB_PATH = '/data/consultas.db' if os.path.exists('/data') else 'consultas.db'

def iniciar_banco() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registro_placas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            dados TEXT NOT NULL,
            data_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao', '0')")
    conn.commit()
    conn.close()

def salvar_consulta(chave_busca: str, dados: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO registro_placas (placa, dados) VALUES (?, ?)', (chave_busca, dados))
    conn.commit()
    conn.close()

def buscar_consulta(chave_busca: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT dados FROM registro_placas WHERE placa = ? ORDER BY data_consulta DESC LIMIT 1', (chave_busca,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None

def is_manutencao() -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'manutencao'")
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] == '1' if resultado else False

def toggle_manutencao() -> None:
    atual = is_manutencao()
    novo_valor = '0' if atual else '1'
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracoes SET valor = ? WHERE chave = 'manutencao'", (novo_valor,))
    conn.commit()
    conn.close()

# ==========================================
# EVENTOS DE INICIALIZAÇÃO
# ==========================================
@app.on_event("startup")
async def startup_event():
    iniciar_banco()
    print(f"Iniciando {len(SESSOES_STRINGS)} contas do Telegram via StringSession...")
    
    for idx, session_str in enumerate(SESSOES_STRINGS):
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.start()
            await fila_clientes.put(client)
            print(f"✅ Conta {idx + 1} conectada e pronta na fila!")
        except Exception as e:
            print(f"❌ Erro ao conectar a conta {idx + 1}: {e}")
            
    print("🚀 Todas as contas operacionais!")

# ==========================================
# ROTAS DA APLICAÇÃO (ENDPOINTS FRONTEND)
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def serve_html():
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    status_manutencao = "true" if is_manutencao() else "false"
    script_injetado = f"<script>window.SISTEMA_EM_MANUTENCAO = {status_manutencao};</script>\n</head>"
    return html.replace("</head>", script_injetado)

# ==========================================
# MÓDULO 1: CONSULTA DE PLACAS
# ==========================================
@app.get("/api/consultar/{placa}")
async def consultar_placa(placa: str, request: Request):
    if is_manutencao():
        return {"sucesso": False, "dados": "🛠️ **SISTEMA EM MANUTENÇÃO!**\n\nNossos servidores estão em ajuste."}
        
    placa = placa.upper()
    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    tempo_atual = time.time()
    ultimo_tempo = cooldowns_por_ip.get(ip_cliente, 0)
    
    try:
        dados_salvos = buscar_consulta(placa)
        if dados_salvos and "Consultando" not in dados_salvos:
            return {"sucesso": True, "dados": dados_salvos, "cache": True}

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {"sucesso": False, "dados": f"🚨 Aguarde mais {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos."}

        # Mock de Desenvolvimento
        if AMBIENTE == "desenvolvimento":
            await asyncio.sleep(2)
            resposta_mock = f"🕵️ **CONSULTA DE PLACA**\n\n• **Placa:** `{placa}`\n• **Situação:** `NORMAL`\n• **Roubo / Furto:** `NAO`"
            salvar_consulta(placa, resposta_mock)
            cooldowns_por_ip[ip_cliente] = time.time()
            return {"sucesso": True, "dados": resposta_mock, "cache": False}

        cliente_atual = await fila_clientes.get()
        try:
            if not cliente_atual.is_connected(): await cliente_atual.connect()
            
            await cliente_atual.send_message(BOT_USERNAME, f'/placa {placa}')
            resposta_final = None
            
            for _ in range(15):
                await asyncio.sleep(2)
                messages = await cliente_atual.get_messages(BOT_USERNAME, limit=1)
                if messages and messages[0].text:
                    texto = messages[0].text
                    if texto.startswith('/placa') or "Consultando..." in texto: continue
                    resposta_final = texto
                    break
            
            if resposta_final:
                # Tratamento da resposta (Corta tudo a partir de "👤 Usuário")
                if "👤 Usuário" in resposta_final: 
                    resposta_final = resposta_final.split("👤 Usuário")[0].strip()
                
                salvar_consulta(placa, resposta_final)
                cooldowns_por_ip[ip_cliente] = time.time()
                return {"sucesso": True, "dados": resposta_final, "cache": False}
            return {"sucesso": False, "dados": "Tempo esgotado na consulta da placa."}
            
        finally:
            await fila_clientes.put(cliente_atual)
            
    except Exception as e:
        return {"sucesso": False, "dados": f"Erro interno: {str(e)}"}

# ==========================================
# MÓDULO 2: CONSULTA DE CNH (CPF) - BLINDADO
# ==========================================
@app.get("/api/consultar_cnh/{cpf}")
async def consultar_cnh(cpf: str, request: Request):
    if is_manutencao():
        return {"sucesso": False, "erro": "🛠️ SISTEMA EM MANUTENÇÃO!"}

    # Limpa pontuação do CPF
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    if len(cpf_limpo) != 11:
        return {"sucesso": False, "erro": "CPF inválido. Digite os 11 números corretamente."}

    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    tempo_atual = time.time()
    ultimo_tempo = cooldowns_por_ip.get(ip_cliente, 0)

    try:
        # 1. VERIFICA O CACHE PRIMEIRO (Evita ir no Telegram se já consultou antes)
        dados_salvos = buscar_consulta(f"CPF_{cpf_limpo}")
        if dados_salvos and "Consultando" not in dados_salvos:
            caminho_foto = f"static/cnh/cnh_{cpf_limpo}.jpg"
            if os.path.exists(caminho_foto): # Só usa o cache se a foto ainda existir na pasta
                return {
                    "sucesso": True, 
                    "dados": dados_salvos,
                    "foto": f"/{caminho_foto}",
                    "cache": True
                }

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {"sucesso": False, "erro": f"Aguarde {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos."}

        # Mock de Desenvolvimento
        if AMBIENTE == "desenvolvimento":
            await asyncio.sleep(3)
            cooldowns_por_ip[ip_cliente] = time.time()
            return {
                "sucesso": True, 
                "dados": f"🕵️ DADOS DA CNH\n\n**CPF:** {cpf_limpo}\n**Nome:** USUÁRIO TESTE ARCSYS",
                "foto": "/static/cnh.png"
            }

        cliente_atual = await fila_clientes.get()
        try:
            if not cliente_atual.is_connected(): await cliente_atual.connect()
            
            # Envia o Comando
            await cliente_atual.send_message(BOT_USERNAME, f'/cpf {cpf_limpo}')
            
            # ESPERA INTELIGENTE PELOS BOTÕES
            msg_botoes = None
            for _ in range(15):
                await asyncio.sleep(2)
                mensagens = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens:
                    if msg.buttons: 
                        # VALIDAÇÃO: Garante que o menu é do CPF que pedimos
                        numeros_menu = ''.join(filter(str.isdigit, msg.text or ""))
                        if cpf_limpo in numeros_menu:
                            msg_botoes = msg
                            break
                if msg_botoes: break
                    
            if not msg_botoes:
                return {"sucesso": False, "erro": "O bot oficial demorou muito para carregar o menu. Tente novamente."}

            # Clicar no botão CNH
            clicou = False
            for linha in msg_botoes.buttons:
                for botao in linha:
                    if "CNH" in botao.text.upper():
                        await botao.click() 
                        clicou = True
                        break
                if clicou: break

            if not clicou:
                return {"sucesso": False, "erro": "Opção CNH indisponível para este CPF."}

            # ESPERA INTELIGENTE PELA FOTO COM VALIDAÇÃO ANTI-CRUZA DE DADOS
            msg_foto = None
            for _ in range(45): 
                await asyncio.sleep(2)
                mensagens_finais = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens_finais:
                    if msg.photo and msg.text:
                        # O SEGREDO: Só pega a foto se o texto dela contiver o CPF pesquisado!
                        numeros_legenda = ''.join(filter(str.isdigit, msg.text))
                        if cpf_limpo in numeros_legenda:
                            msg_foto = msg
                            break
                if msg_foto: break

            if not msg_foto:
                return {"sucesso": False, "erro": "O servidor oficial está congestionado (demorou mais de 1 min). Tente novamente."}

            # Baixa a mídia
            os.makedirs("static/cnh", exist_ok=True)
            caminho_salvo = f"static/cnh/cnh_{cpf_limpo}.jpg"
            await cliente_atual.download_media(msg_foto, file=caminho_salvo)

            dados_texto = msg_foto.text or "Sem dados adicionais."
            
            # TESOURA INFALÍVEL: Corta tudo a partir do emoji de busto 👤
            if "👤" in dados_texto: 
                dados_texto = dados_texto.split("👤")[0].strip()

            # Salva no DB
            salvar_consulta(f"CPF_{cpf_limpo}", dados_texto)
            cooldowns_por_ip[ip_cliente] = time.time()

            return {
                "sucesso": True,
                "dados": dados_texto,
                "foto": f"/{caminho_salvo}"
            }

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception as e:
        return {"sucesso": False, "erro": f"Falha na comunicação: {str(e)}"}

# ==========================================
# ROTAS DO DASHBOARD ADMIN E CONTROLES
# ==========================================
@app.get("/admin/toggle")
async def alternar_status(token: str):
    if token != ADMIN_TOKEN: return "<h1>Acesso Negado</h1>"
    toggle_manutencao()
    return RedirectResponse(url=f"/admin/lista?token={token}")

@app.get("/admin/lista", response_class=HTMLResponse)
async def ver_historico(token: str):
    if token != ADMIN_TOKEN: return "<h1>Acesso Negado</h1>"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT placa, dados, data_consulta FROM registro_placas ORDER BY data_consulta DESC LIMIT 100')
    rows = cursor.fetchall()
    conn.close()

    status_atual = is_manutencao()
    cor_borda = "#e74c3c" if status_atual else "#2ecc71"
    status_texto = "EM MANUTENÇÃO" if status_atual else "ONLINE"
    btn_texto = "LIGAR SISTEMA" if status_atual else "DESLIGAR SISTEMA"
    btn_cor = "#27ae60" if status_atual else "#c0392b"

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Dashboard ARCSYS</title>
        <style>
            body {{ background:#0e1621; color:white; font-family:sans-serif; padding:40px; }}
            .celula-dados {{ max-width: 400px; max-height: 150px; overflow-y: auto; background: #17212b; padding: 10px; font-size: 0.85em; white-space: pre-wrap; border-left: 3px solid #5288c1; }}
            .painel-controle {{ background: #17212b; padding: 20px; border-radius: 8px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; border-left: 6px solid {cor_borda}; }}
            .btn-power {{ background-color: {btn_cor}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="painel-controle">
            <div><h2 style="margin: 0;">Painel de Controle</h2><p style="color: {cor_borda};">Status: {status_texto}</p></div>
            <a href="/admin/toggle?token={token}" class="btn-power">{btn_texto}</a>
        </div>
        <h2>📊 Relatório de Consultas</h2>
        <table border="1" style="width:100%; border-collapse:collapse; border-color: #242f3d;">
            <tr style="background:#5288c1;"><th style="padding:15px;">Chave</th><th style="padding:15px;">Dados</th><th style="padding:15px;">Data</th></tr>
    """
    for row in rows:
        html += f"<tr><td style='padding:15px; text-align:center;'>{row[0]}</td><td style='padding:15px;'><div class='celula-dados'>{row[1]}</div></td><td style='padding:15px; text-align:center;'>{row[2]}</td></tr>"
    
    html += "</table></body></html>"
    return html