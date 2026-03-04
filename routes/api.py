import os
import time
import asyncio
import urllib.request
import urllib.parse
import json
import re
from fastapi import APIRouter, Request
from database import buscar_consulta, salvar_consulta, is_manutencao, is_manutencao_modulo
import base64

router = APIRouter()

# Configurações do Bot e Segurança
BOT_USERNAME = os.getenv('BOT_USERNAME', '')
AMBIENTE = os.getenv("AMBIENTE", "producao")
TURNSTILE_SECRET_KEY = os.getenv('TURNSTILE_SECRET_KEY', '')
TEMPO_COOLDOWN = 120

# Estado Compartilhado
fila_clientes = asyncio.Queue()

cooldowns_placa = {}
cooldowns_cnh = {}
cooldowns_cpf = {}

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

# ==========================================
# MÓDULO 1: CONSULTA DE PLACAS
# ==========================================
@router.get("/api/consultar/{placa}")
async def consultar_placa(placa: str, request: Request):
    if is_manutencao() or is_manutencao_modulo('placa'):
        return {"sucesso": False, "erro": "🛠️ MÓDULO EM MANUTENÇÃO!"}
        
    placa = placa.upper()
    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    
    # 🛡️ BARREIRA DE SEGURANÇA (BOTS E SCRAPERS)
    token_turnstile = request.headers.get("X-Turnstile-Token")
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {"sucesso": False, "erro": "🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente."}

    tempo_atual = time.time()
    ultimo_tempo = cooldowns_placa.get(ip_cliente, 0)
    
    try:
        dados_salvos = buscar_consulta(placa)
        if dados_salvos and "Consultando" not in dados_salvos:
            return {"sucesso": True, "dados": dados_salvos, "cache": True}

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {"sucesso": False, "erro": f"🚨 Aguarde mais {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos."}

        if AMBIENTE == "desenvolvimento":
            await asyncio.sleep(2)
            resposta_mock = f"🕵️ **CONSULTA DE PLACA**\n\n• **Placa:** `{placa}`\n• **Situação:** `NORMAL`\n• **Roubo / Furto:** `NAO`"
            salvar_consulta(placa, resposta_mock)
            cooldowns_placa[ip_cliente] = time.time()
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
                resposta_final = sanitizar_resposta(resposta_final)
                salvar_consulta(placa, resposta_final)
                cooldowns_placa[ip_cliente] = time.time()
                return {"sucesso": True, "dados": resposta_final, "cache": False}
            return {"sucesso": False, "erro": "Tempo esgotado na consulta da placa."}
            
        finally:
            await fila_clientes.put(cliente_atual)
            
    except Exception as e:
        return {"sucesso": False, "erro": f"Erro interno: {str(e)}"}

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

    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    
    # 🛡️ BARREIRA DE SEGURANÇA (BOTS E SCRAPERS)
    token_turnstile = request.headers.get("X-Turnstile-Token")
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {"sucesso": False, "erro": "🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente."}

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
            return {"sucesso": True, "dados": f"🕵️ DADOS DA CNH\n\n**CPF:** {cpf_limpo}\n**Nome:** USUÁRIO TESTE ARCSYS", "foto": "/static/img/cnh.png"}

        cliente_atual = await fila_clientes.get()
        try:
            if not cliente_atual.is_connected(): await cliente_atual.connect()
            
            await cliente_atual.send_message(BOT_USERNAME, f'/cpf {cpf_limpo}')
            
            msg_botoes = None
            for _ in range(15):
                await asyncio.sleep(2)
                mensagens = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens:
                    if msg.buttons: 
                        numeros_menu = ''.join(filter(str.isdigit, msg.text or ""))
                        if cpf_limpo in numeros_menu:
                            msg_botoes = msg
                            break
                if msg_botoes: break
                    
            if not msg_botoes:
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
                return {"sucesso": False, "erro": "Opção CNH indisponível para este documento."}

            msg_foto = None
            for _ in range(45): 
                await asyncio.sleep(2)
                mensagens_finais = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens_finais:
                    if msg.photo and msg.text:
                        numeros_legenda = ''.join(filter(str.isdigit, msg.text))
                        if cpf_limpo in numeros_legenda:
                            msg_foto = msg
                            break
                if msg_foto: break

            if not msg_foto:
                return {"sucesso": False, "erro": "O servidor principal está congestionado. Tente novamente."}

            # 📥 BAIXA A FOTO TEMPORARIAMENTE
            os.makedirs("static/cnh", exist_ok=True)
            caminho_salvo = f"static/cnh/cnh_{cpf_limpo}.jpg"
            await cliente_atual.download_media(msg_foto, file=caminho_salvo)

            # 🖼️ CONVERTE PARA BASE64
            with open(caminho_salvo, "rb") as image_file:
                foto_b64 = "data:image/jpeg;base64," + base64.b64encode(image_file.read()).decode('utf-8')
            
            # 🧹 APAGA A FOTO FÍSICA IMEDIATAMENTE APÓS CONVERTER
            try:
                os.remove(caminho_salvo)
            except Exception as e:
                pass # Se der erro ao apagar, ignora e segue a vida

            # 🛡️ BLINDAGEM DA FONTE APLICADA
            dados_texto = msg_foto.text or "Sem dados adicionais."
            dados_texto = sanitizar_resposta(dados_texto)

            # 📦 EMPACOTA E SALVA NO BANCO (DADOS + FOTO EM BASE64)
            pacote_salvar = json.dumps({"texto": dados_texto, "foto": foto_b64})
            salvar_consulta(f"CPF_{cpf_limpo}", pacote_salvar)
            
            cooldowns_cnh[ip_cliente] = time.time()

            return {"sucesso": True, "dados": dados_texto, "foto": foto_b64}

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception as e:
        return {"sucesso": False, "erro": f"Falha na comunicação: {str(e)}"}
    
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

    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    
    # 🛡️ BARREIRA DE SEGURANÇA (BOTS E SCRAPERS)
    token_turnstile = request.headers.get("X-Turnstile-Token")
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {"sucesso": False, "erro": "🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente."}

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

    except Exception as e:
        return {"sucesso": False, "erro": f"Falha na comunicação: {str(e)}"}