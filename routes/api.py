import os
import time
import asyncio
from fastapi import APIRouter, Request
from database import is_manutencao, buscar_consulta, salvar_consulta

router = APIRouter()

# Configurações do Bot
BOT_USERNAME = os.getenv('BOT_USERNAME', '')
AMBIENTE = os.getenv("AMBIENTE", "producao")
TEMPO_COOLDOWN = 120

# Estado Compartilhado
fila_clientes = asyncio.Queue()

cooldowns_placa = {}
cooldowns_cnh = {}
cooldowns_cpf = {}

# ==========================================
# MÓDULO 1: CONSULTA DE PLACAS
# ==========================================
@router.get("/api/consultar/{placa}")
async def consultar_placa(placa: str, request: Request):
    if is_manutencao():
        return {"sucesso": False, "dados": "🛠️ **SISTEMA EM MANUTENÇÃO!**\n\nNossos servidores estão em ajuste."}
        
    placa = placa.upper()
    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    tempo_atual = time.time()
    ultimo_tempo = cooldowns_placa.get(ip_cliente, 0)
    
    try:
        dados_salvos = buscar_consulta(placa)
        if dados_salvos and "Consultando" not in dados_salvos:
            return {"sucesso": True, "dados": dados_salvos, "cache": True}

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {"sucesso": False, "dados": f"🚨 Aguarde mais {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos."}

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
                if "👤 Usuário" in resposta_final: 
                    resposta_final = resposta_final.split("👤 Usuário")[0].strip()
                salvar_consulta(placa, resposta_final)
                cooldowns_placa[ip_cliente] = time.time()
                return {"sucesso": True, "dados": resposta_final, "cache": False}
            return {"sucesso": False, "dados": "Tempo esgotado na consulta da placa."}
            
        finally:
            await fila_clientes.put(cliente_atual)
            
    except Exception as e:
        return {"sucesso": False, "dados": f"Erro interno: {str(e)}"}

# ==========================================
# MÓDULO 2: CONSULTA DE CNH (CPF)
# ==========================================
@router.get("/api/consultar_cnh/{cpf}")
async def consultar_cnh(cpf: str, request: Request):
    if is_manutencao():
        return {"sucesso": False, "erro": "🛠️ SISTEMA EM MANUTENÇÃO!"}

    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    if len(cpf_limpo) != 11:
        return {"sucesso": False, "erro": "CPF inválido. Digite os 11 números corretamente."}

    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    tempo_atual = time.time()
    ultimo_tempo = cooldowns_cnh.get(ip_cliente, 0)

    try:
        dados_salvos = buscar_consulta(f"CPF_{cpf_limpo}")
        if dados_salvos and "Consultando" not in dados_salvos:
            caminho_foto = f"static/cnh/cnh_{cpf_limpo}.jpg"
            if os.path.exists(caminho_foto):
                return {"sucesso": True, "dados": dados_salvos, "foto": f"/{caminho_foto}", "cache": True}

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
                return {"sucesso": False, "erro": "O bot oficial demorou muito para carregar o menu. Tente novamente."}

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
                return {"sucesso": False, "erro": "O servidor oficial está congestionado. Tente novamente."}

            os.makedirs("static/cnh", exist_ok=True)
            caminho_salvo = f"static/cnh/cnh_{cpf_limpo}.jpg"
            await cliente_atual.download_media(msg_foto, file=caminho_salvo)

            dados_texto = msg_foto.text or "Sem dados adicionais."
            if "👤" in dados_texto: 
                dados_texto = dados_texto.split("👤")[0].strip()

            salvar_consulta(f"CPF_{cpf_limpo}", dados_texto)
            cooldowns_cnh[ip_cliente] = time.time()

            return {"sucesso": True, "dados": dados_texto, "foto": f"/{caminho_salvo}"}

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception as e:
        return {"sucesso": False, "erro": f"Falha na comunicação: {str(e)}"}
    
    
# ==========================================
# MÓDULO 3: CONSULTA DE DADOS (CPF / SISREG)
# ==========================================
@router.get("/api/consultar_dados_cpf/{cpf}")
async def consultar_dados_cpf(cpf: str, request: Request):
    if is_manutencao():
        return {"sucesso": False, "erro": "🛠️ SISTEMA EM MANUTENÇÃO!"}

    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    if len(cpf_limpo) != 11:
        return {"sucesso": False, "erro": "CPF inválido. Digite os 11 números corretamente."}

    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host).split(",")[0].strip()
    tempo_atual = time.time()
    ultimo_tempo = cooldowns_cpf.get(ip_cliente, 0)

    try:
        # 1. Busca no Cache (Note que a chave mudou para SISREG_ para não conflitar com a CNH)
        dados_salvos = buscar_consulta(f"SISREG_{cpf_limpo}")
        if dados_salvos and "Consultando" not in dados_salvos:
            return {"sucesso": True, "dados": dados_salvos, "cache": True}

        # 2. Verifica Cooldown
        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {"sucesso": False, "erro": f"Aguarde {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos."}

        # 3. Módulo de Desenvolvimento / Teste Local
        if AMBIENTE == "desenvolvimento":
            await asyncio.sleep(3)
            cooldowns_cpf[ip_cliente] = time.time()
            return {"sucesso": True, "dados": f"🕵️ DADOS SISREG-III\n\n**CPF:** {cpf_limpo}\n**Nome:** ARCANGELO O MESTRE\n**Situação:** REGULAR\n**Score:** 999"}

        # =======================================
        # COMUNICAÇÃO COM O TELEGRAM
        # =======================================
        cliente_atual = await fila_clientes.get()
        try:
            if not cliente_atual.is_connected(): await cliente_atual.connect()
            
            # 4. Envia o comando do CPF
            await cliente_atual.send_message(BOT_USERNAME, f'/cpf {cpf_limpo}')
            
            # 5. Espera o Menu aparecer
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
                            texto_menu_original = msg.text # Salva o texto do menu para comparar depois
                            break
                if msg_botoes: break
                    
            if not msg_botoes:
                return {"sucesso": False, "erro": "O bot oficial demorou muito para carregar o menu. Tente novamente."}

            # 6. Clica no botão SISREG
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

            # 7. Espera o Bot editar a mensagem com os resultados
            dados_texto = None
            for _ in range(30): 
                await asyncio.sleep(2)
                # Puxa a mesma mensagem de novo para ver se o bot editou ela
                msg_editada = await cliente_atual.get_messages(BOT_USERNAME, ids=msg_botoes.id)
                
                # Se o texto for diferente do menu original, significa que o relatório chegou!
                if msg_editada and msg_editada.text and msg_editada.text != texto_menu_original:
                    dados_texto = msg_editada.text
                    break
                
                # Plano B: Se o bot mandou uma MENSAGEM NOVA em vez de editar
                mensagens_novas = await cliente_atual.get_messages(BOT_USERNAME, limit=2)
                for m in mensagens_novas:
                    if m.id > msg_botoes.id and m.text and cpf_limpo in ''.join(filter(str.isdigit, m.text)):
                        dados_texto = m.text
                        break
                
                if dados_texto: break

            if not dados_texto:
                return {"sucesso": False, "erro": "O servidor do SISREG demorou para responder. Tente novamente."}

            # 8. Limpa lixos do bot (propagandas, botões de voltar, etc)
            if "👤" in dados_texto: 
                dados_texto = dados_texto.split("👤")[0].strip()

            # 9. Salva no Cache e libera
            salvar_consulta(f"SISREG_{cpf_limpo}", dados_texto)
            cooldowns_cpf[ip_cliente] = time.time()

            return {"sucesso": True, "dados": dados_texto}

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception as e:
        return {"sucesso": False, "erro": f"Falha na comunicação: {str(e)}"}