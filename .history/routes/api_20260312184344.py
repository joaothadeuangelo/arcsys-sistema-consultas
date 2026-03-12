import os
from dotenv import load_dotenv
load_dotenv()
import httpx
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
GONZALES_API_TOKEN = os.getenv('GONZALES_API_TOKEN', '')
TEMPO_COOLDOWN = 120

# Estado Compartilhado
fila_clientes = asyncio.Queue()

cooldowns_placa = {}
cooldowns_cnh = {}
cooldowns_cpf = {}
cooldown_comparador = {}

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

        # 🚀 REQUISIÇÃO DIRETA À API GONZALES
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get("https://apis.gonzalesdev.shop/", params={
                "token": GONZALES_API_TOKEN,
                "r": "serpro",
                "placa": placa
            }, headers=headers)

        if response.status_code != 200:
            corpo_log = response.text[:500] if len(response.text) > 500 else response.text
            print(f"ERRO GONZALES STATUS: {response.status_code} - BODY: {corpo_log}")
            return {"sucesso": False, "erro": "Não foi possível consultar esta placa no momento. Tente novamente."}

        dados_api = response.json()

        if isinstance(dados_api, dict) and dados_api.get("erro"):
            print(f"ERRO GONZALES API: {dados_api}")
            return {"sucesso": False, "erro": "Placa não encontrada ou indisponível no momento."}

        # 🛡️ VALIDAÇÃO ESTRUTURAL: Só salva no cache se o retorno parecer dados reais de veículo
        if not isinstance(dados_api, dict) or not any(k in dados_api for k in ("chassi", "placa_mercosul", "placa_antiga", "codigoRenavam", "descricaoMarcaModelo")):
            print(f"GONZALES RETORNO INESPERADO (não é dados de veículo): {str(dados_api)[:300]}")
            return {"sucesso": False, "erro": "Resposta inválida do sistema de consulta. Tente novamente."}

        # Salva o JSON integral no banco para cache futuro
        salvar_consulta(placa, json.dumps(dados_api))
        cooldowns_placa[ip_cliente] = time.time()

        return {"sucesso": True, "dados": dados_api, "cache": False}
            
    except Exception as e:
        # 🛡️ Sanitiza a mensagem: exceções httpx podem conter a URL completa com o token na query string
        msg_erro = re.sub(r'token=[^&\s]+', 'token=***', str(e))
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
                erro_limpo = sanitizar_resposta(erro_bot) # Limpa o @ do bot, caso venha junto
                return {"sucesso": False, "erro": erro_limpo}

            if not msg_resultado:
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
                except Exception as e:
                    pass # Se der erro ao apagar, ignora e segue a vida

            # 🛡️ BLINDAGEM DA FONTE APLICADA
            dados_texto = msg_resultado.text or "Sem dados adicionais."
            dados_texto = sanitizar_resposta(dados_texto)

            # 📦 EMPACOTA E SALVA NO BANCO (DADOS + FOTO EM BASE64 SE TIVER)
            pacote_salvar = json.dumps({"texto": dados_texto, "foto": foto_b64})
            salvar_consulta(f"CPF_{cpf_limpo}", pacote_salvar)
            
            cooldowns_cnh[ip_cliente] = time.time()

            return {"sucesso": True, "dados": dados_texto, "foto": foto_b64}

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception:
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
            
            # 8. Captura a resposta (que agora deve ser o JSON com a task_id)
            try:
                dados_retorno = response.json()
            except:
                dados_retorno = response.text 

            # 9. LOG DE USO: registra consultas do Similar Face no mesmo histórico dos outros módulos
            if response.status_code == 200:
                chave_log = f"SIMILAR_FACE_{ip_cliente}"
                try:
                    if isinstance(dados_retorno, (dict, list)):
                        payload_log = json.dumps(dados_retorno)
                    else:
                        payload_log = json.dumps({
                            "status": "Busca facial realizada",
                            "resumo": str(dados_retorno)[:500]
                        })
                    salvar_consulta(chave_log, payload_log)
                except Exception as e:
                    # Falha de log não deve quebrar a resposta do usuário
                    print(f"FALHA AO REGISTRAR LOG SIMILAR FACE: {e}")
                
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
async def checar_status_facial(task_id: str, request: Request):
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