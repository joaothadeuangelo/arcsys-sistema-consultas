import os
from dotenv import load_dotenv
load_dotenv()
import httpx
import time
import asyncio
import itertools
import urllib.request
import urllib.parse
import json
import re
import unicodedata
from fastapi import APIRouter, Request
from database import buscar_consulta, salvar_consulta, is_manutencao, is_manutencao_modulo, registrar_evento_telemetria_background
import base64
import aiohttp
from bs4 import BeautifulSoup

router = APIRouter()

# Configurações do Bot e Segurança
BOT_USERNAME = os.getenv('BOT_USERNAME', '')
AMBIENTE = os.getenv("AMBIENTE", "producao")
TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY', '')
tokens_str = os.getenv("GONZALES_API_TOKENS", "")
lista_tokens = [t.strip() for t in tokens_str.split(",") if t.strip()]

# Fallback seguro: mantém compatibilidade com o token antigo (singular).
if not lista_tokens:
    token_legado = os.getenv('GONZALES_API_TOKEN', '').strip()
    if token_legado:
        lista_tokens = [token_legado]
    else:
        # Evita crash no startup caso o env ainda não esteja configurado.
        lista_tokens = [""]

token_cycle = itertools.cycle(lista_tokens)
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


@router.get('/api/admin/status-circuit-breaker')
async def status_circuit_breaker(request: Request):
    """Endpoint leve de monitoramento do contador de falhas consecutivas."""
    estado = getattr(request.app.state, 'falhas_consecutivas', {})

    # Resposta mínima: expõe apenas os contadores dos módulos monitorados.
    placa = int(estado.get('placa', 0)) if isinstance(estado, dict) else 0
    cnh = int(estado.get('cnh', 0)) if isinstance(estado, dict) else 0

    return {'placa': placa, 'cnh': cnh}


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
    ip_cloudflare = request.headers.get("CF-Connecting-IP")
    if ip_cloudflare:
        return ip_cloudflare
        
    # 2º Fallback padrão se não passar pelo Cloudflare
    ip_proxy = request.headers.get("X-Forwarded-For")
    if ip_proxy:
        return ip_proxy.split(",")[0].strip()
        
    return request.client.host

# ==========================================
# 🛡️ MOTOR DE BLINDAGEM DE FONTE (WHITE-LABEL)
# ==========================================
def sanitizar_resposta(texto: str) -> str:
    if not texto: return "Erro ao processar os dados."

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
    if not token: return False
    # Se a chave não estiver no .env (ex: rodando local rápido), permite passar para não quebrar seu teste
    if not TURNSTILE_SECRET_KEY: return True 
    
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
            url_resultado = extrair_url_resultado_completo(msg)

            if url_resultado:
                return {'texto': texto, 'url_resultado': url_resultado}

            if texto and any(trecho in texto.lower() for trecho in ('nome:', 'cpf:', 'consulta conclu', 'total de resultados')):
                return {'texto': texto, 'url_resultado': ''}

    return None

# ==========================================
# MÓDULO 1: CONSULTA DE PLACAS (API DIRETA)
# ==========================================
@router.get("/api/consultar/{placa}")
async def consultar_placa(placa: str, request: Request):
    if is_manutencao() or is_manutencao_modulo('placa'):
        return {"sucesso": False, "erro": "🛠️ MÓDULO EM MANUTENÇÃO!"}
        
    placa = placa.upper()
    
    # 🛡️ VALIDAÇÃO DE ENTRADA: Rejeita inputs absurdos antes de qualquer processamento
    if len(placa) > 10:
        return {"sucesso": False, "erro": "Formato de placa inválido."}
    
    ip_cliente = obter_ip_real(request)
    
    # 🛡️ BARREIRA DE SEGURANÇA (BOTS E SCRAPERS)
    token_turnstile = request.headers.get("X-Turnstile-Token")
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {"sucesso": False, "erro": "🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente."}

    registrar_evento_telemetria_background("uso_modulo", "placa", ip_cliente)

    tempo_atual = time.time()
    ultimo_tempo = cooldowns_placa.get(ip_cliente, 0)
    
    try:
        # 📦 CACHE: Tenta recuperar do banco (salvo como JSON string)
        dados_salvos = buscar_consulta(placa)
        if dados_salvos and "Consultando" not in dados_salvos:
            try:
                dados_cache = json.loads(dados_salvos)
                return {"sucesso": True, "dados": dados_cache, "cache": True}
            except json.JSONDecodeError:
                pass

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {"sucesso": False, "erro": f"🚨 Aguarde mais {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos."}

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive"
        }

        current_token = next(token_cycle)

        # 🚀 REQUISIÇÃO DIRETA À API GONZALES
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get("https://apis.gonzalesdev.shop/", params={
                "token": current_token,
                "r": "serpro",
                "placa": placa
            }, headers=headers)

        if response.status_code in (500, 502, 503):
            await _registrar_falha_modulo(request, 'placa')

        if response.status_code != 200:
            corpo_log = response.text[:500] if len(response.text) > 500 else response.text
            corpo_log = mascarar_tokens_em_texto(corpo_log)
            print(f"ERRO GONZALES STATUS: {response.status_code} - BODY: {corpo_log}")
            return {"sucesso": False, "erro": "Não foi possível consultar esta placa no momento. Tente novamente."}

        dados_api = response.json()

        if isinstance(dados_api, dict) and dados_api.get("erro"):
            print(f"ERRO GONZALES API: {mascarar_tokens_em_texto(dados_api)}")
            return {"sucesso": False, "erro": "Placa não encontrada ou indisponível no momento."}

        # 🛡️ VALIDAÇÃO ESTRUTURAL: Só salva no cache se o retorno parecer dados reais de veículo
        if not isinstance(dados_api, dict) or not any(k in dados_api for k in ("chassi", "placa_mercosul", "placa_antiga", "codigoRenavam", "descricaoMarcaModelo")):
            print(f"GONZALES RETORNO INESPERADO (não é dados de veículo): {str(dados_api)[:300]}")
            return {"sucesso": False, "erro": "Resposta inválida do sistema de consulta. Tente novamente."}

        # Salva o JSON integral no banco para cache futuro
        salvar_consulta(placa, json.dumps(dados_api))
        cooldowns_placa[ip_cliente] = time.time()
        await _resetar_falhas_modulo(request, 'placa')

        return {"sucesso": True, "dados": dados_api, "cache": False}
            
    except Exception as e:
        await _registrar_falha_modulo(request, 'placa')
        # 🛡️ Sanitiza a mensagem: exceções httpx podem conter a URL completa com o token na query string
        msg_erro = mascarar_tokens_em_texto(str(e))
        print(f"EXCEÇÃO INTERNA ROTA PLACA: {msg_erro}")
        return {"sucesso": False, "erro": "Erro interno no servidor. Tente novamente."}

# ==========================================
# MÓDULO 2: CONSULTA DE CNH (CPF)
# ==========================================
@router.get("/api/consultar_cnh/{cpf}")
async def consultar_cnh(cpf: str, request: Request):
    if is_manutencao() or is_manutencao_modulo('cnh'):
        return {"sucesso": False, "erro": "🛠️ MÓDULO EM MANUTENÇÃO!"}

    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    if len(cpf_limpo) != 11:
        return {"sucesso": False, "erro": "CPF inválido. Digite os 11 números corretamente."}

    ip_cliente = obter_ip_real(request)
    
    # 🛡️ BARREIRA DE SEGURANÇA (BOTS E SCRAPERS)
    token_turnstile = request.headers.get("X-Turnstile-Token")
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {"sucesso": False, "erro": "🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente."}

    registrar_evento_telemetria_background("uso_modulo", "cnh", ip_cliente)

    tempo_atual = time.time()
    ultimo_tempo = cooldowns_cnh.get(ip_cliente, 0)

    try:
        dados_salvos = buscar_consulta(f"CPF_{cpf_limpo}")
        if dados_salvos and "Consultando" not in dados_salvos:
            # 📦 TENTA DESEMPACOTAR O JSON (Novo formato com Base64)
            try:
                dados_json = json.loads(dados_salvos)
                return {
                    "sucesso": True, 
                    "dados": dados_json.get("texto", ""), 
                    "foto": dados_json.get("foto", ""), 
                    "cache": True
                }
            except json.JSONDecodeError:
                # Fallback: Se for uma consulta antiga (só texto), tenta achar a foto na pasta
                caminho_foto = f"static/cnh/cnh_{cpf_limpo}.jpg"
                if os.path.exists(caminho_foto):
                    return {"sucesso": True, "dados": dados_salvos, "foto": f"/{caminho_foto}", "cache": True}
                return {"sucesso": True, "dados": dados_salvos, "cache": True}

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {"sucesso": False, "erro": f"Aguarde {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos."}

        if AMBIENTE == "desenvolvimento":
            await asyncio.sleep(3)
            cooldowns_cnh[ip_cliente] = time.time()
            await _resetar_falhas_modulo(request, 'cnh')
            return {"sucesso": True, "dados": f"🕵️ DADOS DA CNH\n\n**CPF:** {cpf_limpo}\n**Nome:** USUÁRIO TESTE ARCSYS", "foto": "/static/img/cnh.png"}

        cliente_atual = await fila_clientes.get()
        try:
            if not cliente_atual.is_connected(): await cliente_atual.connect()
            
            await cliente_atual.send_message(BOT_USERNAME, f'/cpf {cpf_limpo}')
            
            msg_botoes = None
            texto_menu_original = "" # 💡 Guarda o texto original do menu
            for _ in range(15):
                await asyncio.sleep(2)
                mensagens = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens:
                    if msg.buttons: 
                        numeros_menu = ''.join(filter(str.isdigit, msg.text or ""))
                        if cpf_limpo in numeros_menu:
                            msg_botoes = msg
                            texto_menu_original = msg.text or "" # Salva o texto
                            break
                if msg_botoes: break
                    
            if not msg_botoes:
                await _registrar_falha_modulo(request, 'cnh')
                return {"sucesso": False, "erro": "O sistema central demorou para responder. Tente novamente."}

            clicou = False
            for linha in msg_botoes.buttons:
                for botao in linha:
                    if "CNH" in botao.text.upper():
                        await botao.click() 
                        clicou = True
                        break
                if clicou: break

            if not clicou:
                await _registrar_falha_modulo(request, 'cnh')
                return {"sucesso": False, "erro": "Opção CNH indisponível para este documento."}

            msg_resultado = None 
            erro_bot = None # 💡 Variável para capturar a resposta de erro

            for _ in range(45): 
                await asyncio.sleep(2)
                
                # 1. Verifica se a mensagem original foi EDITADA (comum quando o bot manda só texto ou erro)
                msg_editada = await cliente_atual.get_messages(BOT_USERNAME, ids=msg_botoes.id)
                if msg_editada and msg_editada.text and msg_editada.text != texto_menu_original:
                    texto_editado = msg_editada.text
                    texto_lower = texto_editado.lower()
                    
                    # 🚨 RADAR DE ERRO
                    if "não possui" in texto_lower or "⚠️" in texto_lower or "não encontrad" in texto_lower:
                        erro_bot = texto_editado
                        break
                    
                    msg_resultado = msg_editada
                    break

                # 2. Verifica se chegou uma mensagem NOVA (com foto ou apenas texto/erro)
                mensagens_finais = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens_finais:
                    if msg.id > msg_botoes.id:
                        texto_legenda = msg.text or ""
                        
                        # 🚨 RADAR DE ERRO
                        texto_lower = texto_legenda.lower()
                        if "não possui" in texto_lower or "⚠️" in texto_lower or "não encontrad" in texto_lower:
                            erro_bot = texto_legenda
                            break
                        
                        # Se não for erro, procura os dados do CPF
                        numeros_legenda = ''.join(filter(str.isdigit, texto_legenda))
                        if cpf_limpo in numeros_legenda:
                            msg_resultado = msg
                            break
                
                # Interrompe o loop se achou o resultado OU se achou um erro
                if msg_resultado or erro_bot: break

            # 🛑 SE O BOT RETORNOU ERRO, DEVOLVE NA HORA PARA O USUÁRIO
            if erro_bot:
                await _registrar_falha_modulo(request, 'cnh')
                erro_limpo = sanitizar_resposta(erro_bot) # Limpa o @ do bot, caso venha junto
                return {"sucesso": False, "erro": erro_limpo}

            if not msg_resultado:
                await _registrar_falha_modulo(request, 'cnh')
                return {"sucesso": False, "erro": "O servidor principal está congestionado. Tente novamente."}

            foto_b64 = ""
            
            # 💡 Só tenta baixar a foto SE existir uma foto na mensagem (nova arquitetura híbrida)
            if msg_resultado.photo:
                # 📥 BAIXA A FOTO TEMPORARIAMENTE
                os.makedirs("static/cnh", exist_ok=True)
                caminho_salvo = f"static/cnh/cnh_{cpf_limpo}.jpg"
                await cliente_atual.download_media(msg_resultado, file=caminho_salvo)

                # 🖼️ CONVERTE PARA BASE64
                with open(caminho_salvo, "rb") as image_file:
                    foto_b64 = "data:image/jpeg;base64," + base64.b64encode(image_file.read()).decode('utf-8')
                
                # 🧹 APAGA A FOTO FÍSICA IMEDIATAMENTE APÓS CONVERTER
                try:
                    os.remove(caminho_salvo)
                except Exception:
                    pass # Se der erro ao apagar, ignora e segue a vida

            # 🛡️ BLINDAGEM DA FONTE APLICADA
            dados_texto = msg_resultado.text or "Sem dados adicionais."
            dados_texto = sanitizar_resposta(dados_texto)

            # 📦 EMPACOTA E SALVA NO BANCO (DADOS + FOTO EM BASE64 SE TIVER)
            pacote_salvar = json.dumps({"texto": dados_texto, "foto": foto_b64})
            salvar_consulta(f"CPF_{cpf_limpo}", pacote_salvar)
            
            cooldowns_cnh[ip_cliente] = time.time()
            await _resetar_falhas_modulo(request, 'cnh')

            return {"sucesso": True, "dados": dados_texto, "foto": foto_b64}

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception:
        await _registrar_falha_modulo(request, 'cnh')
        return {"sucesso": False, "erro": "Erro interno no servidor. Tente novamente."}
    
# ==========================================
# MÓDULO 3: CONSULTA DE DADOS (CPF / SISREG)
# ==========================================
@router.get("/api/consultar_dados_cpf/{cpf}")
async def consultar_dados_cpf(cpf: str, request: Request):
    if is_manutencao() or is_manutencao_modulo('cpf'):
        return {"sucesso": False, "erro": "🛠️ MÓDULO EM MANUTENÇÃO!"}

    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    if len(cpf_limpo) != 11:
        return {"sucesso": False, "erro": "CPF inválido. Digite os 11 números corretamente."}

    ip_cliente = obter_ip_real(request)
    
    # 🛡️ BARREIRA DE SEGURANÇA (BOTS E SCRAPERS)
    token_turnstile = request.headers.get("X-Turnstile-Token")
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {"sucesso": False, "erro": "🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente."}

    registrar_evento_telemetria_background("uso_modulo", "cpf", ip_cliente)

    tempo_atual = time.time()
    ultimo_tempo = cooldowns_cpf.get(ip_cliente, 0)

    try:
        dados_salvos = buscar_consulta(f"SISREG_{cpf_limpo}")
        if dados_salvos and "Consultando" not in dados_salvos:
            return {"sucesso": True, "dados": dados_salvos, "cache": True}

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {"sucesso": False, "erro": f"Aguarde {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos."}

        if AMBIENTE == "desenvolvimento":
            await asyncio.sleep(3)
            cooldowns_cpf[ip_cliente] = time.time()
            return {"sucesso": True, "dados": f"🕵️ DADOS SISREG-III\n\n**CPF:** {cpf_limpo}\n**Nome:** ARCANGELO O MESTRE\n**Situação:** REGULAR\n**Score:** 999"}

        cliente_atual = await fila_clientes.get()
        try:
            if not cliente_atual.is_connected(): await cliente_atual.connect()
            
            await cliente_atual.send_message(BOT_USERNAME, f'/cpf {cpf_limpo}')
            
            msg_botoes = None
            texto_menu_original = ""
            for _ in range(15):
                await asyncio.sleep(2)
                mensagens = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens:
                    if msg.buttons: 
                        numeros_menu = ''.join(filter(str.isdigit, msg.text or ""))
                        if cpf_limpo in numeros_menu:
                            msg_botoes = msg
                            texto_menu_original = msg.text
                            break
                if msg_botoes: break
                    
            if not msg_botoes:
                # Ajuste de mensagem para não mencionar o bot oficial
                return {"sucesso": False, "erro": "O sistema central demorou muito para carregar as opções. Tente novamente."}

            clicou = False
            for linha in msg_botoes.buttons:
                for botao in linha:
                    if "SISREG" in botao.text.upper():
                        await botao.click() 
                        clicou = True
                        break
                if clicou: break

            if not clicou:
                return {"sucesso": False, "erro": "Opção SISREG-III indisponível para este CPF."}

            dados_texto = None
            for _ in range(30): 
                await asyncio.sleep(2)
                msg_editada = await cliente_atual.get_messages(BOT_USERNAME, ids=msg_botoes.id)
                
                if msg_editada and msg_editada.text and msg_editada.text != texto_menu_original:
                    dados_texto = msg_editada.text
                    break
                
                mensagens_novas = await cliente_atual.get_messages(BOT_USERNAME, limit=2)
                for m in mensagens_novas:
                    if m.id > msg_botoes.id and m.text and cpf_limpo in ''.join(filter(str.isdigit, m.text)):
                        dados_texto = m.text
                        break
                
                if dados_texto: break

            if not dados_texto:
                return {"sucesso": False, "erro": "O servidor do SISREG demorou para responder. Tente novamente."}

            # 🛡️ BLINDAGEM DA FONTE APLICADA AQUI (Substitui o `split` manual)
            dados_texto = sanitizar_resposta(dados_texto)

            salvar_consulta(f"SISREG_{cpf_limpo}", dados_texto)
            cooldowns_cpf[ip_cliente] = time.time()

            return {"sucesso": True, "dados": dados_texto}

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception:
        return {"sucesso": False, "erro": "Erro interno no servidor. Tente novamente."}


# ==========================================
# MÓDULO 4: COMPARADOR FACIAL (PROXY)
# ==========================================
@router.get('/api/consultar/nome/{nome_buscado}')
async def consultar_nome(nome_buscado: str, request: Request):
    if is_manutencao() or is_manutencao_modulo('nome'):
        return {'sucesso': False, 'erro': '🛠️ MÓDULO EM MANUTENÇÃO!'}

    nome_limpo = re.sub(r'\s+', ' ', (nome_buscado or '')).strip()
    if len(nome_limpo) < 3:
        return {'sucesso': False, 'erro': 'Digite ao menos 3 caracteres para consultar por nome.'}
    if len(nome_limpo) > 80:
        return {'sucesso': False, 'erro': 'Nome muito longo para consulta.'}

    ip_cliente = obter_ip_real(request)
    token_turnstile = request.headers.get('X-Turnstile-Token')
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {'sucesso': False, 'erro': '🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente.'}

    registrar_evento_telemetria_background('uso_modulo', 'nome', ip_cliente)

    tempo_atual = time.time()
    ultimo_tempo = cooldowns_nome.get(ip_cliente, 0)
    if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
        return {'sucesso': False, 'erro': f'Aguarde {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos.'}

    cache_key = f'NOME_{nome_limpo.upper()}'

    try:
        dados_salvos = buscar_consulta(cache_key)
        if dados_salvos and 'Consultando' not in dados_salvos:
            try:
                cache_json = json.loads(dados_salvos)
                if isinstance(cache_json, dict) and isinstance(cache_json.get('resultados'), list):
                    return {
                        'sucesso': True,
                        'resultados': cache_json['resultados'],
                        'fonte': cache_json.get('fonte', 'cache'),
                        'cache': True
                    }
            except json.JSONDecodeError:
                pass

        if AMBIENTE == 'desenvolvimento':
            await asyncio.sleep(1)
            mock = [
                {
                    'nome': 'USUARIO TESTE ARCSYS',
                    'cpf': '000.000.000-00',
                    'sexo': 'N/I',
                    'data_nascimento': '01/01/1990'
                }
            ]
            cooldowns_nome[ip_cliente] = time.time()
            return {'sucesso': True, 'resultados': mock, 'fonte': 'mock_dev'}

        cliente_atual = await fila_clientes.get()
        try:
            if not cliente_atual.is_connected():
                await cliente_atual.connect()

            msg_comando = await cliente_atual.send_message(BOT_USERNAME, f'/nome {nome_limpo}')
            retorno = await aguardar_retorno_consulta_nome(cliente_atual, msg_comando.id)

            if not retorno:
                return {'sucesso': False, 'erro': 'O sistema central demorou para responder. Tente novamente.'}

            resultados = []
            fonte = 'chat'

            if retorno.get('url_resultado'):
                resultados = await extrair_resultados_telegraph(retorno['url_resultado'])
                fonte = 'telegraph'

            if not resultados:
                texto_retorno = retorno.get('texto', '')
                resultados = parse_resultados_nome(texto_retorno)
                if resultados:
                    fonte = 'chat'

            if not resultados:
                return {'sucesso': False, 'erro': 'Nenhum resultado estruturado foi encontrado para este nome.'}

            pacote_salvar = json.dumps({'resultados': resultados, 'fonte': fonte}, ensure_ascii=False)
            salvar_consulta(cache_key, pacote_salvar)

            cooldowns_nome[ip_cliente] = time.time()
            return {'sucesso': True, 'resultados': resultados, 'fonte': fonte, 'cache': False}

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception as e:
        print(f'EXCEÇÃO INTERNA ROTA NOME: {mascarar_tokens_em_texto(str(e))}')
        return {'sucesso': False, 'erro': 'Erro interno no servidor. Tente novamente.'}


@router.post("/api/comparar_facial")
async def comparar_facial(request: Request):
    # 1. Verifica se o sistema está em manutenção
    if is_manutencao():
        return {"sucesso": False, "erro": "🛠️ MÓDULO EM MANUTENÇÃO!"}

    # 2. Puxa o IP do cliente (anti-spoofing)
    ip_cliente = obter_ip_real(request)

    # 🛡️ TRAVA DE COOLDOWN (RATE LIMIT DE 60 SEGUNDOS)
    tempo_atual = time.time()
    tempo_ultimo_uso = cooldown_comparador.get(ip_cliente, 0)
    tempo_restante = 60 - (tempo_atual - tempo_ultimo_uso)
    
    if tempo_restante > 0:
        return {"sucesso": False, "erro": f"⏳ Aguarde {int(tempo_restante)} segundos para fazer uma nova comparação."}

    # 3. Validação de Segurança do Turnstile
    token_turnstile = request.headers.get("X-Turnstile-Token")
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {"sucesso": False, "erro": "🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente."}

    registrar_evento_telemetria_background("uso_modulo", "comparador", ip_cliente)

    # 4. Puxa a URL segura do arquivo .env
    url_destino = os.getenv("URL_MOTOR_FACIAL")
    if not url_destino:
        return {"sucesso": False, "erro": "URL do motor facial não configurada no servidor."}

    try:
        # 5. Recebe os arquivos do frontend do ARCSYS
        form_data = await request.form()
        imagem_base = form_data.get("imagem_base")
        imagens_lote = form_data.getlist("imagens_lote")

        # 🛡️ VALIDAÇÃO BACK-END: Arquivos ausentes
        if not imagem_base or not imagens_lote:
            return {"sucesso": False, "erro": "Imagens ausentes. Envie a base e pelo menos uma imagem no lote."}

        # 🛡️ VALIDAÇÃO BACK-END: Limite Máximo de 250 imagens
        if len(imagens_lote) > 250:
            return {"sucesso": False, "erro": f"⚠️ Tentativa de abuso detectada! O limite máximo é de 250 imagens (Você enviou {len(imagens_lote)})."}

        # 🛡️ VALIDAÇÃO BACK-END: Limite de 10MB por arquivo (Anti-OOM)
        TAMANHO_MAX_ARQUIVO = 10 * 1024 * 1024  # 10MB
        conteudo_base_preview = await imagem_base.read()
        if len(conteudo_base_preview) > TAMANHO_MAX_ARQUIVO:
            return {"sucesso": False, "erro": "⚠️ A imagem base excede o limite de 10MB."}
        # Rebobina o ponteiro do arquivo para leitura posterior
        await imagem_base.seek(0)

        # Atualiza o tempo do último uso deste IP (só bloqueia o tempo se passar das validações)
        cooldown_comparador[ip_cliente] = tempo_atual

        # 6. Prepara os arquivos com as ETIQUETAS EXATAS que o servidor parceiro exige
        files = []
        
        # 🎯 ETIQUETA CORRETA: base_file
        conteudo_base = await imagem_base.read()
        files.append(("base_file", (imagem_base.filename, conteudo_base, imagem_base.content_type)))

        # 🎯 ETIQUETA CORRETA: compare_files[]
        for img in imagens_lote:
            conteudo_lote = await img.read()
            files.append(("compare_files[]", (img.filename, conteudo_lote, img.content_type)))

        # 7. Faz o POST direto para o endpoint de processamento (compare.php)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url_destino, files=files)

            if response.status_code != 200:
                corpo_log = response.text[:500] if len(response.text) > 500 else response.text
                corpo_log = mascarar_tokens_em_texto(corpo_log)
                print(f"ERRO SIMILAR FACE STATUS: {response.status_code} - BODY: {corpo_log}")
                if ip_cliente in cooldown_comparador:
                    del cooldown_comparador[ip_cliente]
                return {"sucesso": False, "erro": "O servidor de biometria está temporariamente indisponível ou sobrecarregado. Tente novamente."}
            
            # 8. Captura a resposta (que agora deve ser o JSON com a task_id)
            try:
                dados_retorno = response.json()
            except:
                if ip_cliente in cooldown_comparador:
                    del cooldown_comparador[ip_cliente]
                return {"sucesso": False, "erro": "Resposta inválida do motor de biometria. Tente novamente."}

            # 9. LOG DE USO: registra consultas do Similar Face no mesmo histórico dos outros módulos
            if response.status_code == 200:
                chave_log = f"SIMILAR_FACE_{ip_cliente}"
                try:
                    if isinstance(dados_retorno, (dict, list)):
                        payload_log = json.dumps(dados_retorno)
                        if len(payload_log) > 20000:
                            payload_log = json.dumps({
                                "status": "Busca facial realizada",
                                "resumo": "Payload extenso truncado para proteção de armazenamento.",
                                "tamanho_original": len(json.dumps(dados_retorno))
                            })
                    else:
                        payload_log = json.dumps({
                            "status": "Busca facial realizada",
                            "resumo": str(dados_retorno)[:500]
                        })
                    salvar_consulta(chave_log, payload_log)
                except Exception as e:
                    # Falha de log não deve quebrar a resposta do usuário
                    print(f"FALHA AO REGISTRAR LOG SIMILAR FACE: {mascarar_tokens_em_texto(e)}")
                
            return {"sucesso": True, "resultados": dados_retorno}

    # 🔒 BLINDAGEM MÁXIMA: Erros mascarados para não vazar IP/URL
    except Exception:
        # Se der erro no servidor, liberamos o IP para tentar de novo
        if ip_cliente in cooldown_comparador:
            del cooldown_comparador[ip_cliente]
        return {"sucesso": False, "erro": "O servidor de biometria está temporariamente indisponível ou sobrecarregado. Tente novamente."}


# ==========================================
# ROTA AUXILIAR: RADAR DO STATUS
# ==========================================
@router.get("/api/comparar_facial/status/{task_id}")
async def checar_status_facial(task_id: str):
    if is_manutencao():
        return {"sucesso": False, "erro": "🛠️ MÓDULO EM MANUTENÇÃO!"}

    url_destino = os.getenv("URL_MOTOR_FACIAL")
    if not url_destino:
        return {"sucesso": False, "erro": "URL do motor facial não configurada."}

    # 🛡️ VALIDAÇÃO: Sanitiza o task_id para impedir SSRF e injeção de parâmetros na URL
    if not re.match(r'^[a-zA-Z0-9_-]{1,128}$', task_id):
        return {"sucesso": False, "erro": "ID de tarefa inválido."}
    
    url_check = f"{url_destino}?task_id={task_id}&offset=0&limit=250"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url_check)
            
            # Tenta ler a resposta como JSON
            try:
                dados_json = response.json()
            except:
                return {"sucesso": True, "concluido": False} # Se não for JSON, ainda não tá pronto
            
            # 🎯 O VEREDITO: Lê a chave "task_status" que você encontrou na espionagem
            if dados_json.get("task_status") == "SUCCESS":
                return {"sucesso": True, "concluido": True, "dados": dados_json}
            else:
                return {"sucesso": True, "concluido": False}

    # 🔒 BLINDAGEM MÁXIMA: Erros mascarados para não vazar IP/URL
    except Exception:
        return {"sucesso": False, "erro": "Perda de conexão com o motor facial durante a verificação."}