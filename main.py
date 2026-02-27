from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
import asyncio
import sqlite3
import os
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

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
# Define onde o banco vai ser salvo. Se a pasta /data existir (Railway), salva lá.
# Se não existir (no seu PC), salva na mesma pasta do código.
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
    
    # Inicia cada conta usando o texto gigante (StringSession) e joga na fila
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
async def consultar_placa(placa: str):
    placa = placa.upper()
    
    try:
        # 1. Verifica no banco primeiro
        dados_salvos = buscar_consulta(placa)
        if dados_salvos:
            return {"sucesso": True, "dados": dados_salvos, "cache": True}

        # 2. Pega uma conta livre na fila
        cliente_atual = await fila_clientes.get()
        
        try:
            # Envia o comando para o bot
            await cliente_atual.send_message(bot_username, f'/placa {placa}')
            await asyncio.sleep(4)
            
            # Pega a resposta
            messages = await cliente_atual.get_messages(bot_username, limit=1)
            
            if messages and messages[0].text:
                resposta = messages[0].text
                
                # Limpa o rodapé
                if "👤 Usuário:" in resposta:
                    resposta = resposta.split("👤 Usuário:")[0].strip()
                    
                salvar_consulta(placa, resposta)
                return {"sucesso": True, "dados": resposta, "cache": False}
            else:
                return {"sucesso": False, "dados": "O bot não respondeu a tempo."}
                
        finally:
            # 3. Devolve a conta para a fila, mesmo se der erro
            await fila_clientes.put(cliente_atual)
            
    except Exception as e:
        return {"sucesso": False, "dados": f"Erro interno: {str(e)}"}