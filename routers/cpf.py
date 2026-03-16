import time
import asyncio

from fastapi import APIRouter, Request

from database import buscar_consulta, salvar_consulta, is_manutencao, is_manutencao_modulo, registrar_evento_telemetria_background
from .shared import (
    BOT_USERNAME,
    AMBIENTE,
    TEMPO_COOLDOWN,
    fila_clientes,
    cooldowns_cpf,
    obter_ip_real,
    verificar_turnstile,
    sanitizar_resposta,
)

router = APIRouter(prefix='/api')


@router.get('/consultar_dados_cpf/{cpf}')
async def consultar_dados_cpf(cpf: str, request: Request):
    if is_manutencao() or is_manutencao_modulo('cpf'):
        return {'sucesso': False, 'erro': '🛠️ MÓDULO EM MANUTENÇÃO!'}

    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    if len(cpf_limpo) != 11:
        return {'sucesso': False, 'erro': 'CPF inválido. Digite os 11 números corretamente.'}

    ip_cliente = obter_ip_real(request)

    # 🛡️ BARREIRA DE SEGURANÇA (BOTS E SCRAPERS)
    token_turnstile = request.headers.get('X-Turnstile-Token')
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {'sucesso': False, 'erro': '🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente.'}

    registrar_evento_telemetria_background('uso_modulo', 'cpf', ip_cliente)

    tempo_atual = time.time()
    ultimo_tempo = cooldowns_cpf.get(ip_cliente, 0)

    try:
        dados_salvos = buscar_consulta(f'SISREG_{cpf_limpo}')
        if dados_salvos and 'Consultando' not in dados_salvos:
            return {'sucesso': True, 'dados': dados_salvos, 'cache': True}

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {'sucesso': False, 'erro': f'Aguarde {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos.'}

        if AMBIENTE == 'desenvolvimento':
            await asyncio.sleep(3)
            cooldowns_cpf[ip_cliente] = time.time()
            return {'sucesso': True, 'dados': f'🕵️ DADOS SISREG-III\n\n**CPF:** {cpf_limpo}\n**Nome:** ARCANGELO O MESTRE\n**Situação:** REGULAR\n**Score:** 999'}

        cliente_atual = await fila_clientes.get()
        try:
            if not cliente_atual.is_connected():
                await cliente_atual.connect()

            await cliente_atual.send_message(BOT_USERNAME, f'/cpf {cpf_limpo}')

            msg_botoes = None
            texto_menu_original = ''
            for _ in range(15):
                await asyncio.sleep(2)
                mensagens = await cliente_atual.get_messages(BOT_USERNAME, limit=5)
                for msg in mensagens:
                    if msg.buttons:
                        numeros_menu = ''.join(filter(str.isdigit, msg.text or ''))
                        if cpf_limpo in numeros_menu:
                            msg_botoes = msg
                            texto_menu_original = msg.text
                            break
                if msg_botoes:
                    break

            if not msg_botoes:
                # Ajuste de mensagem para não mencionar o bot oficial
                return {'sucesso': False, 'erro': 'O sistema central demorou muito para carregar as opções. Tente novamente.'}

            clicou = False
            for linha in msg_botoes.buttons:
                for botao in linha:
                    if 'SISREG' in botao.text.upper():
                        await botao.click()
                        clicou = True
                        break
                if clicou:
                    break

            if not clicou:
                return {'sucesso': False, 'erro': 'Opção SISREG-III indisponível para este CPF.'}

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

                if dados_texto:
                    break

            if not dados_texto:
                return {'sucesso': False, 'erro': 'O servidor do SISREG demorou para responder. Tente novamente.'}

            # 🛡️ BLINDAGEM DA FONTE APLICADA AQUI (Substitui o `split` manual)
            dados_texto = sanitizar_resposta(dados_texto)

            salvar_consulta(f'SISREG_{cpf_limpo}', dados_texto)
            cooldowns_cpf[ip_cliente] = time.time()

            return {'sucesso': True, 'dados': dados_texto}

        finally:
            await fila_clientes.put(cliente_atual)

    except Exception:
        return {'sucesso': False, 'erro': 'Erro interno no servidor. Tente novamente.'}
