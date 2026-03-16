import re
import time
import json
import asyncio

from fastapi import APIRouter, Request

from database import buscar_consulta, salvar_consulta, is_manutencao, is_manutencao_modulo, registrar_evento_telemetria_background
from .shared import (
    BOT_USERNAME,
    AMBIENTE,
    TEMPO_COOLDOWN,
    fila_clientes,
    cooldowns_nome,
    mascarar_tokens_em_texto,
    obter_ip_real,
    verificar_turnstile,
    parse_resultados_nome,
    extrair_resultados_telegraph,
    aguardar_retorno_consulta_nome,
)

router = APIRouter(prefix='/api')


@router.get('/consultar/nome/{nome_buscado}')
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
