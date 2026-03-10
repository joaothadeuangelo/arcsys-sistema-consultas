import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from telethon import TelegramClient
from telethon.sessions import StringSession

# 1. PRIMEIRO DE TUDO: Carregar as senhas do .env!
load_dotenv()
API_ID = int(os.getenv('API_ID', 0))  
API_HASH = os.getenv('API_HASH', '')

SESSOES_STRINGS = [
    value.strip() for key, value in os.environ.items() 
    if key.startswith('SESSAO_') and value.strip()
]

# 2. SÓ DEPOIS: Importar os nossos módulos (Agora eles enxergam as senhas)
from database import iniciar_banco
from routes.views import router as views_router
from routes.api import router as api_router, fila_clientes
from routes.admin import router as admin_router

AMBIENTE = os.getenv('AMBIENTE', 'producao')

# 🛡️ PRODUÇÃO: Desabilita /docs e /redoc (evita expor a API publicamente)
if AMBIENTE == 'producao':
    app = FastAPI(title="ARCSYS - Central de Consultas", docs_url=None, redoc_url=None, openapi_url=None)
else:
    app = FastAPI(title="ARCSYS - Central de Consultas")

# ... (Daqui pra baixo o código do main.py continua normal, começando pelo app.mount) ...

# Servindo arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# 🛡️ Middleware de Limite de Body (Anti-OOM)
MAX_BODY_SIZE = 300 * 1024 * 1024  # 300MB (250 imagens de ~1MB)

@app.middleware("http")
async def limitar_tamanho_body(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse({"sucesso": False, "erro": "Payload excede o limite permitido."}, status_code=413)
    return await call_next(request)

# Middleware de Redirecionamento
@app.middleware("http")
async def redirecionar_dominio_antigo(request: Request, call_next):
    host_atual = request.headers.get("host", "")
    if "auto-bot-production-9044.up.railway.app" in host_atual:
        nova_url = f"https://placa.arcangelopainel.xyz{request.url.path}"
        if request.url.query: nova_url += f"?{request.url.query}"
        return RedirectResponse(url=nova_url, status_code=301)
    return await call_next(request)

# Startup das contas do Telegram
@app.on_event("startup")
async def startup_event():
    iniciar_banco()
    print(f"Iniciando {len(SESSOES_STRINGS)} contas do Telegram...")
    for idx, session_str in enumerate(SESSOES_STRINGS):
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                await fila_clientes.put(client)
                print(f"✅ Conta {idx + 1} conectada e pronta!")
            else:
                print(f"❌ Conta {idx + 1} deslogada. Ignorando...")
        except Exception as e:
            print(f"❌ Erro na conta {idx + 1}: {e}")
            
    print(f"🚀 {fila_clientes.qsize()} contas operacionais!")

# Plugando as Rotas na Aplicação Principal
app.include_router(views_router)
app.include_router(api_router)
app.include_router(admin_router)

# Healthcheck leve — responde instantaneamente, antes de qualquer middleware pesado
@app.get("/health")
async def healthcheck():
    return {"status": "ok"}