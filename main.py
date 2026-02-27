from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
import sqlite3
import os
import time
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

api_id = int(os.getenv('API_ID'))  
api_hash = os.getenv('API_HASH')
bot_username = os.getenv('BOT_USERNAME')

# Busca todas as variáveis no .env que começam com 'SESSAO_'
sessoes_strings = []
for key, value in os.environ.items():
    if key.startswith('SESSAO_') and value.strip():
        sessoes_strings.append(value.strip())

# Inicializa o FastAPI
app = FastAPI()

# Criamos a Fila que vai guardar nossos clientes
fila_clientes = asyncio.Queue()

# --- CONTROLE DE COOLDOWN (BACKEND) ---
cooldowns_por_ip = {}
TEMPO_COOLDOWN = 60 # 60 segundos de espera

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
DB_PATH = '/data/consultas.db' if os.path.exists('/data') else 'consultas.db'

def iniciar_banco():
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

def salvar_consulta(placa: str, dados: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO registro_placas (placa, dados) VALUES (?, ?)', (placa, dados))
    conn.commit()
    conn.close()

def buscar_consulta(placa: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT dados FROM registro_placas WHERE placa = ? ORDER BY data_consulta DESC LIMIT 1', (placa,))
    resultado = cursor.fetchone()
    conn.close()
    
    if resultado:
        return resultado[0]
    return None
# --------------------------------------

@app.on_event("startup")
async def startup_event():
    iniciar_banco()
    
    print(f"Iniciando {len(sessoes_strings)} contas do Telegram via StringSession...")
    
    for idx, session_str in enumerate(sessoes_strings):
        try:
            client = TelegramClient(StringSession(session_str), api_id, api_hash)
            await client.start()
            await fila_clientes.put(client)
            print(f"✅ Conta {idx + 1} conectada e pronta na fila!")
        except Exception as e:
            print(f"❌ Erro ao conectar a conta {idx + 1}: {e}")
            
    print("🚀 Todas as contas operacionais!")

@app.get("/", response_class=HTMLResponse)
async def serve_html():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/consultar/{placa}")
async def consultar_placa(placa: str, request: Request):
    placa = placa.upper()
    
    # Descobre o IP real do usuário
    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host)
    if ip_cliente:
        ip_cliente = ip_cliente.split(",")[0].strip()
        
    tempo_atual = time.time()
    ultimo_tempo = cooldowns_por_ip.get(ip_cliente, 0)
    
    try:
        # 1. Verifica no banco primeiro
        dados_salvos = buscar_consulta(placa)
        if dados_salvos:
            return {"sucesso": True, "dados": dados_salvos, "cache": True}

        # 2. Cooldown
        tempo_passado = tempo_atual - ultimo_tempo
        if tempo_passado < TEMPO_COOLDOWN:
            tempo_restante = int(TEMPO_COOLDOWN - tempo_passado)
            return {"sucesso": False, "dados": f"🚨 Calma lá, apressadinho! O sistema é de graça.\nAguarde mais {tempo_restante} segundos para fazer uma nova consulta no bot."}

        # 3. Pega uma conta livre na fila
        cliente_atual = await fila_clientes.get()
        
        try:
            # --- CORREÇÃO: HEALTH CHECK DA CONEXÃO ---
            if not cliente_atual.is_connected():
                print("⚠️ Conta desconectada detectada. Forçando reconexão...")
                await cliente_atual.connect()
            # -----------------------------------------
            
            # Envia o comando
            await cliente_atual.send_message(bot_username, f'/placa {placa}')
            await asyncio.sleep(4)
            
            # Pega a resposta
            messages = await cliente_atual.get_messages(bot_username, limit=1)
            
            if messages and messages[0].text:
                resposta = messages[0].text
                
                if "👤 Usuário:" in resposta:
                    resposta = resposta.split("👤 Usuário:")[0].strip()
                    
                salvar_consulta(placa, resposta)
                
                cooldowns_por_ip[ip_cliente] = time.time()
                
                return {"sucesso": True, "dados": resposta, "cache": False}
            else:
                return {"sucesso": False, "dados": "O bot não respondeu a tempo."}
                
        finally:
            # Devolve a conta para a fila
            await fila_clientes.put(cliente_atual)
            
    except Exception as e:
        return {"sucesso": False, "dados": f"Erro interno de conexão: {str(e)}\nTente novamente em alguns segundos."}