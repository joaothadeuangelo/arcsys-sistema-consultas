import os
import asyncio
import aiohttp
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

# Circuit Breaker passivo: contador simples em memória por módulo crítico.
falhas_consecutivas = {"placa": 0, "cnh": 0}


async def notificar_admin_telegram(modulo: str, erros: int):
    """Envia alerta ao admin quando um módulo acumula falhas consecutivas."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()

    if not bot_token or not admin_chat_id:
        print("[ALERTA TELEGRAM] TELEGRAM_BOT_TOKEN/TELEGRAM_ADMIN_CHAT_ID não configurados.")
        return

    texto_alerta = (
        "🚨 ALERTA DE ESTABILIDADE (ARCSYS)\n"
        f"Módulo: {modulo.upper()}\n"
        f"Falhas consecutivas: {erros}\n"
        "Ação: verificar provedor externo imediatamente."
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": admin_chat_id,
        "text": texto_alerta,
        "disable_web_page_preview": True
    }

    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    detalhe = await response.text()
                    print(f"[ALERTA TELEGRAM] Falha no envio ({response.status}): {detalhe[:300]}")
    except Exception as e:
        print(f"[ALERTA TELEGRAM] Exceção ao notificar admin: {e}")

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
    # Disponibiliza estado e notificador para as rotas sem acoplamento circular.
    app.state.falhas_consecutivas = falhas_consecutivas
    app.state.notificar_admin_telegram = notificar_admin_telegram

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