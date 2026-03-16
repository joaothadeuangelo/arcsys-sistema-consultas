import os
import time
import json
import asyncio
import base64

from fastapi import APIRouter, Request

from database import buscar_consulta, salvar_consulta, is_manutencao, is_manutencao_modulo, registrar_evento_telemetria_background
from .shared import (
    BOT_USERNAME,
    AMBIENTE,
    TEMPO_COOLDOWN,
    fila_clientes,
    cooldowns_cnh,
    _registrar_falha_modulo,
    _resetar_falhas_modulo,
    obter_ip_real,
    verificar_turnstile,
    sanitizar_resposta,
)

router = APIRouter(prefix='/api')


@router.get('/consultar_cnh/{cpf}')
async def consultar_cnh(cpf: str, request: Request):
    if is_manutencao() or is_manutencao_modulo('cnh'):
        return {'sucesso': False, 'erro': '🛠️ MÓDULO EM MANUTENÇÃO!'}

    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    if len(cpf_limpo) != 11:
        return {'sucesso': False, 'erro': 'CPF inválido. Digite os 11 números corretamente.'}

    ip_cliente = obter_ip_real(request)

    # 🛡️ BARREIRA DE SEGURANÇA (BOTS E SCRAPERS)
    token_turnstile = request.headers.get('X-Turnstile-Token')
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {'sucesso': False, 'erro': '🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente.'}

    registrar_evento_telemetria_background('uso_modulo', 'cnh', ip_cliente)

    tempo_atual = time.time()
    ultimo_tempo = cooldowns_cnh.get(ip_cliente, 0)

    try:
        dados_salvos = buscar_consulta(f'CPF_{cpf_limpo}')
        if dados_salvos and 'Consultando' not in dados_salvos:
            # 📦 TENTA DESEMPACOTAR O JSON (Novo formato com Base64)
            try:
                dados_json = json.loads(dados_salvos)
                return {
                    'sucesso': True,
                    'dados': dados_json.get('texto', ''),
                    'foto': dados_json.get('foto', ''),
                    'cache': True
                }
            except json.JSONDecodeError:
                # Fallback: Se for uma consulta antiga (só texto), tenta achar a foto na pasta
                caminho_foto = f'static/cnh/cnh_{cpf_limpo}.jpg'
                if os.path.exists(caminho_foto):
                    return {'sucesso': True, 'dados': dados_salvos, 'foto': f'/{caminho_foto}', 'cache': True}
                return {'sucesso': True, 'dados': dados_salvos, 'cache': True}

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {'sucesso': False, 'erro': f'Aguarde {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos.'}

        if AMBIENTE == 'desenvolvimento':
            await asyncio.sleep(3)
            cooldowns_cnh[ip_cliente] = time.time()
            await _resetar_falhas_modulo(request, 'cnh')
            return {'sucesso': True, 'dados': f'🕵️ DADOS DA CNH\n\n**CPF:** {cpf_limpo}\n**Nome:** USUÁRIO TESTE ARCSYS', 'foto': '/static/img/cnh.png'}

        cliente_atual = await fila_clientes.get()
        try:
            if not cliente_atual.is_connected():
                await cliente_atual.connect()

            await cliente_atual.send_message(BOT_USERNAME, f'/cpf {cpf_limpo}')

            msg_botoes = None
            texto_menu_original = ''  # 💡 Guarda o texto original do menu
            for _ in range(15):
                await asyncio.sleep(2)
                mensagens = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens:
                    if msg.buttons:
                        numeros_menu = ''.join(filter(str.isdigit, msg.text or ''))
                        if cpf_limpo in numeros_menu:
                            msg_botoes = msg
                            texto_menu_original = msg.text or ''  # Salva o texto
                            break
                if msg_botoes:
                    break

            if not msg_botoes:
                await _registrar_falha_modulo(request, 'cnh')
                return {'sucesso': False, 'erro': 'O sistema central demorou para responder. Tente novamente.'}

            clicou = False
            for linha in msg_botoes.buttons:
                for botao in linha:
                    if 'CNH' in botao.text.upper():
                        await botao.click()
                        clicou = True
                        break
                if clicou:
                    break

            if not clicou:
                await _registrar_falha_modulo(request, 'cnh')
                return {'sucesso': False, 'erro': 'Opção CNH indisponível para este documento.'}

            msg_resultado = None
            erro_bot = None  # 💡 Variável para capturar a resposta de erro

            for _ in range(45):
                await asyncio.sleep(2)

                # 1. Verifica se a mensagem original foi EDITADA (comum quando o bot manda só texto ou erro)
                msg_editada = await cliente_atual.get_messages(BOT_USERNAME, ids=msg_botoes.id)
                if msg_editada and msg_editada.text and msg_editada.text != texto_menu_original:
                    texto_editado = msg_editada.text
                    texto_lower = texto_editado.lower()

                    # 🚨 RADAR DE ERRO
                    if 'não possui' in texto_lower or '⚠️' in texto_lower or 'não encontrad' in texto_lower:
                        erro_bot = texto_editado
                        break

                    msg_resultado = msg_editada
                    break

                # 2. Verifica se chegou uma mensagem NOVA (com foto ou apenas texto/erro)
                mensagens_finais = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens_finais:
                    if msg.id > msg_botoes.id:
                        texto_legenda = msg.text or ''

                        # 🚨 RADAR DE ERRO
                        texto_lower = texto_legenda.lower()
                        if 'não possui' in texto_lower or '⚠️' in texto_lower or 'não encontrad' in texto_lower:
                            erro_bot = texto_legenda
                            break

                        # Se não for erro, procura os dados do CPF
                        numeros_legenda = ''.join(filter(str.isdigit, texto_legenda))
                        if cpf_limpo in numeros_legenda:
                            msg_resultado = msg
                            break

                # Interrompe o loop se achou o resultado OU se achou um erro
                if msg_resultado or erro_bot:
                    break

            # 🛑 SE O BOT RETORNOU ERRO, DEVOLVE NA HORA PARA O USUÁRIO
            if erro_bot:
                await _registrar_falha_modulo(request, 'cnh')
                erro_limpo = sanitizar_resposta(erro_bot)  # Limpa o @ do bot, caso venha junto
                return {'sucesso': False, 'erro': erro_limpo}

            if not msg_resultado:
                await _registrar_falha_modulo(request, 'cnh')
                return {'sucesso': False, 'erro': 'O servidor principal está congestionado. Tente novamente.'}

            foto_b64 = ''

            # 💡 Só tenta baixar a foto SE existir uma foto na mensagem (nova arquitetura híbrida)
            if msg_resultado.photo:
                # 📥 BAIXA A FOTO TEMPORARIAMENTE
                os.makedirs('static/cnh', exist_ok=True)
                caminho_salvo = f'static/cnh/cnh_{cpf_limpo}.jpg'
                await cliente_atual.download_media(msg_resultado, file=caminho_salvo)

                # 🖼️ CONVERTE PARA BASE64
                with open(caminho_salvo, 'rb') as image_file:
                    foto_b64 = 'data:image/jpeg;base64,' + base64.b64encode(image_file.read()).decode('utf-8')

                # 🧹 APAGA A FOTO FÍSICA IMEDIATAMENTE APÓS CONVERTER
                try:
                    os.remove(caminho_salvo)
                except Exception:
                    pass  # Se der erro ao apagar, ignora e segue a vida

            # 🛡️ BLINDAGEM DA FONTE APLICADA
            dados_texto = msg_resultado.text or 'Sem dados adicionais.'
            dados_texto = sanitizar_resposta(dados_texto)

            # 📦 EMPACOTA E SALVA NO BANCO (DADOS + FOTO EM BASE64 SE TIVER)
            pacote_salvar = json.dumps({'texto': dados_texto, 'foto': foto_b64})
            salvar_consulta(f'CPF_{cpf_limpo}', pacote_salvar)

            cooldowns_cnh[ip_cliente] = time.time()
            await _resetar_falhas_modulo(request, 'cnh')

            return {'sucesso': True, 'dados': dados_texto, 'foto': foto_b64}

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception:
        await _registrar_falha_modulo(request, 'cnh')
        return {'sucesso': False, 'erro': 'Erro interno no servidor. Tente novamente.'}
