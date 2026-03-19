import os
import asyncio
import urllib.request
import urllib.parse
import json
import re
import unicodedata

import aiohttp
from bs4 import BeautifulSoup
from fastapi import Request

BOT_USERNAME = os.getenv('BOT_USERNAME', '')
AMBIENTE = os.getenv('AMBIENTE', 'producao')
TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY', '')
TEMPO_COOLDOWN = 120

# Estado Compartilhado
fila_clientes = asyncio.Queue()

cooldowns_placa = {}
cooldowns_cnh = {}
cooldowns_cpf = {}
cooldowns_nome = {}
cooldown_comparador = {}


async def _resetar_falhas_modulo(request: Request, modulo: str):
    """Zera o contador de falhas consecutivas após sucesso de chamada externa."""
    estado = getattr(request.app.state, 'falhas_consecutivas', None)
    if isinstance(estado, dict) and modulo in estado:
        estado[modulo] = 0


async def _registrar_falha_modulo(request: Request, modulo: str):
    """Incrementa falhas e dispara alerta no limite sem bloquear resposta ao usuário."""
    estado = getattr(request.app.state, 'falhas_consecutivas', None)
    notificar = getattr(request.app.state, 'notificar_admin_telegram', None)

    if not isinstance(estado, dict) or modulo not in estado:
        return

    estado[modulo] += 1
    # Anti-spam: dispara somente no limiar exato da terceira falha.
    if estado[modulo] == 3:
        erros = estado[modulo]
        if callable(notificar):
            asyncio.create_task(notificar(modulo, erros))


def mascarar_tokens_em_texto(texto: str) -> str:
    if texto is None:
        return ""
    saida = str(texto)
    # token em querystring
    saida = re.sub(r'token=[^&\s]+', 'token=***', saida)
    # token em JSON/texto
    saida = re.sub(r'("token"\s*:\s*")[^"]+(")', r'\1***\2', saida, flags=re.IGNORECASE)
    return saida


# ==========================================
# 🛡️ EXTRAÇÃO SEGURA DE IP (ANTI-SPOOFING)
# ==========================================
def obter_ip_real(request: Request) -> str:
    # 1º Tenta pegar o IP real carimbado pelo Cloudflare (Seguro contra spoofing)
    ip_cloudflare = (request.headers.get("CF-Connecting-IP") or "").strip()
    if ip_cloudflare:
        return ip_cloudflare

    # 2º Railway/outros proxies: pode vir lista "ip_cliente, ip_proxy1, ip_proxy2"
    x_forwarded_for = (request.headers.get("X-Forwarded-For") or "").strip()
    if x_forwarded_for:
        primeiro_ip = x_forwarded_for.split(",", 1)[0].strip()
        if primeiro_ip:
            return primeiro_ip

    return request.client.host if request.client and request.client.host else "anonimo"


# ==========================================
# 🛡️ MOTOR DE BLINDAGEM DE FONTE (WHITE-LABEL)
# ==========================================
def sanitizar_resposta(texto: str) -> str:
    if not texto:
        return "Erro ao processar os dados."

    # 1. Substitui mensagens de erro específicas da fonte por genéricas do ARCSYS
    erros_fonte = ["Não foi possível realizar a consulta", "serviço de consulta de placas está indisponível"]
    if any(erro in texto for erro in erros_fonte):
        return "⚠️ O sistema ARCSYS está passando por instabilidade momentânea neste módulo. Tente novamente em alguns minutos."

    # 2. Arranca o rodapé do usuário/bot (com ou sem o emoji)
    if "👤 Usuário" in texto:
        texto = texto.split("👤 Usuário")[0]
    if "👤" in texto:
        texto = texto.split("👤")[0]

    # 3. Caça e destrói qualquer link do Telegram (t.me, telegram.me)
    texto = re.sub(r'https?://(?:t\.me|telegram\.me)/[^\s]+', '', texto, flags=re.IGNORECASE)

    # 4. Caça e destrói qualquer menção a bots ou canais (@ConsultasGonzalesbot, @GonzalesCanal, etc)
    texto = re.sub(r'@[A-Za-z0-9_]+bot\b', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'@GonzalesCanal\b', '', texto, flags=re.IGNORECASE)

    return texto.strip()


# ==========================================
# 🛡️ MOTOR DE SEGURANÇA: CLOUDFLARE TURNSTILE
# ==========================================
async def verificar_turnstile(token: str, ip: str) -> bool:
    if not token:
        return False
    # Se a chave não estiver no .env (ex: rodando local rápido), permite passar para não quebrar seu teste
    if not TURNSTILE_SECRET_KEY:
        return True

    url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    data = urllib.parse.urlencode({
        'secret': TURNSTILE_SECRET_KEY,
        'response': token,
        'remoteip': ip
    }).encode('utf-8')

    try:
        # Roda a requisição em background para não travar o FastAPI (Alta Performance)
        loop = asyncio.get_event_loop()

        def fetch():
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=5) as response:
                return json.loads(response.read().decode())

        resultado = await loop.run_in_executor(None, fetch)
        return resultado.get("success", False)
    except Exception as e:
        print(f"Erro na validação do Turnstile: {e}")
        return False


def _normalizar_chave(texto: str) -> str:
    if not texto:
        return ""
    base = unicodedata.normalize('NFKD', texto)
    base = base.encode('ascii', 'ignore').decode('ascii').lower()
    base = re.sub(r'[^a-z0-9\s]', ' ', base)
    return ' '.join(base.split())


def _campo_nome_por_label(label: str):
    normalizado = _normalizar_chave(label)

    if 'nome da mae' in normalizado or normalizado == 'mae':
        return 'nome_mae'
    if 'data de nascimento' in normalizado or normalizado.startswith('nascimento'):
        return 'data_nascimento'
    if 'cpf' in normalizado:
        return 'cpf'
    if 'sexo' in normalizado:
        return 'sexo'
    if normalizado.startswith('situacao'):
        return 'situacao'
    if normalizado == 'nome' or normalizado.startswith('nome '):
        return 'nome'
    return None


def _deduplicar_resultados_nome(resultados: list[dict]) -> list[dict]:
    saida = []
    vistos = set()

    for item in resultados:
        nome = (item.get('nome') or '').strip().lower()
        cpf = re.sub(r'\D', '', item.get('cpf') or '')
        chave = (nome, cpf)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(item)

    return saida


def parse_resultados_nome(texto: str) -> list[dict]:
    if not texto:
        return []

    linhas = [linha.strip() for linha in texto.replace('\r', '\n').split('\n')]
    resultados = []
    atual = {}

    for linha in linhas:
        if not linha or ':' not in linha:
            continue

        chave, valor = linha.split(':', 1)
        campo = _campo_nome_por_label(chave)
        if not campo:
            continue

        valor_limpo = valor.strip()
        if not valor_limpo:
            continue

        if campo == 'nome' and atual and any(k in atual for k in ('cpf', 'data_nascimento', 'sexo', 'nome_mae', 'situacao')):
            resultados.append(atual)
            atual = {}

        atual[campo] = valor_limpo

    if atual:
        resultados.append(atual)

    return _deduplicar_resultados_nome(resultados)


def extrair_url_resultado_completo(msg) -> str:
    botoes = getattr(msg, 'buttons', None)
    if not botoes:
        return ""

    for linha in botoes:
        for botao in linha:
            texto_botao = (getattr(botao, 'text', '') or '').strip().lower()
            url_botao = getattr(botao, 'url', '') or ''
            if url_botao and ('resultado completo' in texto_botao or 'ver resultado completo' in texto_botao):
                return url_botao

    return ""


async def extrair_resultados_telegraph(url: str) -> list[dict]:
    if not re.match(r'^https?://(?:telegra\.ph|graph\.org)/', (url or '').strip(), flags=re.IGNORECASE):
        return []

    timeout = aiohttp.ClientTimeout(total=20)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url, allow_redirects=True) as response:
            if response.status != 200:
                return []
            html = await response.text()

    soup = BeautifulSoup(html, 'html.parser')
    container = soup.select_one('.tl_article') or soup.select_one('article') or soup.body
    if not container:
        return []

    texto = container.get_text('\n', strip=True)
    return parse_resultados_nome(texto)


async def aguardar_retorno_consulta_nome(cliente, id_msg_comando: int):
    for _ in range(30):
        await asyncio.sleep(2)
        mensagens = await cliente.get_messages(BOT_USERNAME, limit=8)

        for msg in mensagens:
            if msg.id <= id_msg_comando:
                continue

            texto = (msg.text or '').strip()
            texto_normalizado = texto.lower()
            url_resultado = extrair_url_resultado_completo(msg)

            if texto and 'nome nao encontrado' in _normalizar_chave(texto_normalizado):
                return {'texto': texto, 'url_resultado': '', 'status': 'not_found'}

            if url_resultado:
                return {'texto': texto, 'url_resultado': url_resultado}

            if texto and any(trecho in texto_normalizado for trecho in ('nome:', 'cpf:', 'consulta conclu', 'total de resultados')):
                return {'texto': texto, 'url_resultado': ''}

    return None
