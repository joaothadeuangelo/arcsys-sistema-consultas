import os
import time
import sqlite3
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient
from telethon.sessions import StringSession

# ==========================================
# CONFIGURAÇÕES GERAIS E CREDENCIAIS
# ==========================================
load_dotenv()

API_ID = int(os.getenv('API_ID', 0))  
API_HASH = os.getenv('API_HASH', '')
BOT_USERNAME = os.getenv('BOT_USERNAME', '')
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'mudar_isso_depois')

# Coleta todas as strings de sessão usando List Comprehension
SESSOES_STRINGS = [
    value.strip() for key, value in os.environ.items() 
    if key.startswith('SESSAO_') and value.strip()
]

# ==========================================
# ESTADO DA APLICAÇÃO E RATE LIMIT
# ==========================================
app = FastAPI(title="ARCYS - Consulta de Veículos")
fila_clientes = asyncio.Queue()

cooldowns_por_ip = {}
TEMPO_COOLDOWN = 60 # Tempo de espera em segundos

# ==========================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# ==========================================
DB_PATH = '/data/consultas.db' if os.path.exists('/data') else 'consultas.db'

def iniciar_banco() -> None:
    """Cria a tabela de registros caso não exista."""
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
    conn.commit()
    conn.close()

def salvar_consulta(placa: str, dados: str) -> None:
    """Salva o resultado de uma consulta no banco."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO registro_placas (placa, dados) VALUES (?, ?)', (placa, dados))
    conn.commit()
    conn.close()

def buscar_consulta(placa: str):
    """Verifica se uma placa já foi consultada recentemente."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT dados FROM registro_placas WHERE placa = ? ORDER BY data_consulta DESC LIMIT 1', (placa,))
    resultado = cursor.fetchone()
    conn.close()
    
    return resultado[0] if resultado else None

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
# ROTAS DA APLICAÇÃO (ENDPOINTS)
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def serve_html():
    """Renderiza a página inicial (Frontend)."""
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/consultar/{placa}")
async def consultar_placa(placa: str, request: Request):
    """Endpoint principal de consulta de placas."""
    placa = placa.upper()
    
    # Extração de IP considerando proxies de nuvem (Railway)
    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host)
    if ip_cliente:
        ip_cliente = ip_cliente.split(",")[0].strip()
        
    tempo_atual = time.time()
    ultimo_tempo = cooldowns_por_ip.get(ip_cliente, 0)
    
    try:
        # 1. Verifica Cache (Banco de Dados)
        dados_salvos = buscar_consulta(placa)
        if dados_salvos:
            return {"sucesso": True, "dados": dados_salvos, "cache": True}

        # 2. Verificação de Cooldown (Rate Limit por IP)
        tempo_passado = tempo_atual - ultimo_tempo
        if tempo_passado < TEMPO_COOLDOWN:
            tempo_restante = int(TEMPO_COOLDOWN - tempo_passado)
            return {
                "sucesso": False, 
                "dados": f"🚨 Calma lá, apressadinho! O sistema é de graça.\nAguarde mais {tempo_restante} segundos para fazer uma nova consulta no bot."
            }

        # 3. Processamento via Telegram (Fila)
        cliente_atual = await fila_clientes.get()
        
        try:
            # Health Check da Conexão
            if not cliente_atual.is_connected():
                print("⚠️ Conta desconectada detectada. Forçando reconexão...")
                await cliente_atual.connect()
            
            # Executa a consulta
            await cliente_atual.send_message(BOT_USERNAME, f'/placa {placa}')
            await asyncio.sleep(4)
            messages = await cliente_atual.get_messages(BOT_USERNAME, limit=1)
            
            if messages and messages[0].text:
                resposta = messages[0].text
                
                # Tratamento da resposta (Remoção de rodapé do bot original)
                if "👤 Usuário:" in resposta:
                    resposta = resposta.split("👤 Usuário:")[0].strip()
                    
                salvar_consulta(placa, resposta)
                cooldowns_por_ip[ip_cliente] = time.time()
                
                return {"sucesso": True, "dados": resposta, "cache": False}
            else:
                return {"sucesso": False, "dados": "O bot não respondeu a tempo."}
                
        finally:
            # Garante que a conta retorne para a fila mesmo em caso de erro
            await fila_clientes.put(cliente_atual)
            
    except Exception as e:
        return {
            "sucesso": False, 
            "dados": f"Erro interno de conexão: {str(e)}\nTente novamente em alguns segundos."
        }

@app.get("/admin/lista", response_class=HTMLResponse)
async def ver_historico(token: str):
    """Painel de administração para visualização dos registros no banco."""
    if token != ADMIN_TOKEN:
        return "<h1>Acesso Negado, amigão!</h1>"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT placa, data_consulta FROM registro_placas ORDER BY data_consulta DESC LIMIT 100')
    rows = cursor.fetchall()
    conn.close()

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard ARCYS</title>
    </head>
    <body style="background:#0e1621; color:white; font-family:sans-serif; padding:40px;">
        <h2>📊 Relatório de Consultas - ARCYS</h2>
        <table border="1" style="width:100%; border-collapse:collapse; background:#17212b;">
            <tr style="background:#5288c1;">
                <th style="padding:10px;">Placa</th>
                <th style="padding:10px;">Data/Hora</th>
            </tr>
    """
    for row in rows:
        html += f"<tr><td style='padding:10px; text-align:center;'>{row[0]}</td><td style='padding:10px; text-align:center;'>{row[1]}</td></tr>"
    
    html += """
        </table>
    </body>
    </html>
    """
    return html