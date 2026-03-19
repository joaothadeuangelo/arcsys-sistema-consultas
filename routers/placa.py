import os
import time
import json

import httpx
from fastapi import APIRouter, Request

from database import buscar_consulta, salvar_consulta, is_manutencao, is_manutencao_modulo, registrar_evento_telemetria_background
from .shared import (
    TEMPO_COOLDOWN,
    cooldowns_placa,
    _registrar_falha_modulo,
    _resetar_falhas_modulo,
    mascarar_tokens_em_texto,
    obter_ip_real,
    verificar_turnstile,
)

router = APIRouter(prefix='/api')

token_principal = os.getenv('GONZALES_API_TOKEN', '').strip()

# Compatibilidade: se apenas GONZALES_API_TOKENS estiver definido, usa o ultimo token nao vazio como principal.
if not token_principal:
    tokens_str = os.getenv('GONZALES_API_TOKENS', '')
    lista_tokens = [t.strip() for t in tokens_str.split(',') if t.strip()]
    token_principal = lista_tokens[-1] if lista_tokens else ''


@router.get('/consultar/{placa}')
async def consultar_placa(placa: str, request: Request):
    if is_manutencao() or is_manutencao_modulo('placa'):
        return {'sucesso': False, 'erro': '🛠️ MÓDULO EM MANUTENÇÃO!'}

    placa = placa.upper()

    # 🛡️ VALIDAÇÃO DE ENTRADA: Rejeita inputs absurdos antes de qualquer processamento
    if len(placa) > 10:
        return {'sucesso': False, 'erro': 'Formato de placa inválido.'}

    ip_cliente = obter_ip_real(request)

    # 🛡️ BARREIRA DE SEGURANÇA (BOTS E SCRAPERS)
    token_turnstile = request.headers.get('X-Turnstile-Token')
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {'sucesso': False, 'erro': '🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente.'}

    registrar_evento_telemetria_background('uso_modulo', 'placa', ip_cliente)

    tempo_atual = time.time()
    ultimo_tempo = cooldowns_placa.get(ip_cliente, 0)

    try:
        # 📦 CACHE: Tenta recuperar do banco (salvo como JSON string)
        dados_salvos = buscar_consulta(placa)
        if dados_salvos and 'Consultando' not in dados_salvos:
            try:
                dados_cache = json.loads(dados_salvos)
                return {'sucesso': True, 'dados': dados_cache, 'cache': True}
            except json.JSONDecodeError:
                pass

        if (tempo_atual - ultimo_tempo) < TEMPO_COOLDOWN:
            return {'sucesso': False, 'erro': f'🚨 Aguarde mais {int(TEMPO_COOLDOWN - (tempo_atual - ultimo_tempo))} segundos.'}

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive'
        }

        current_token = token_principal

        # 🚀 REQUISIÇÃO DIRETA À API GONZALES
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get('https://apis.gonzalesdev.shop/', params={
                'token': current_token,
                'r': 'serpro',
                'placa': placa
            }, headers=headers)

        if response.status_code in (500, 502, 503):
            await _registrar_falha_modulo(request, 'placa')

        if response.status_code != 200:
            corpo_log = response.text[:500] if len(response.text) > 500 else response.text
            corpo_log = mascarar_tokens_em_texto(corpo_log)
            print(f'ERRO GONZALES STATUS: {response.status_code} - BODY: {corpo_log}')
            return {'sucesso': False, 'erro': 'Não foi possível consultar esta placa no momento. Tente novamente.'}

        dados_api = response.json()

        if isinstance(dados_api, dict) and dados_api.get('erro'):
            print(f'ERRO GONZALES API: {mascarar_tokens_em_texto(dados_api)}')
            return {'sucesso': False, 'erro': 'Placa não encontrada ou indisponível no momento.'}

        # 🛡️ VALIDAÇÃO ESTRUTURAL: Só salva no cache se o retorno parecer dados reais de veículo
        if not isinstance(dados_api, dict) or not any(k in dados_api for k in ('chassi', 'placa_mercosul', 'placa_antiga', 'codigoRenavam', 'descricaoMarcaModelo')):
            print(f'GONZALES RETORNO INESPERADO (não é dados de veículo): {str(dados_api)[:300]}')
            return {'sucesso': False, 'erro': 'Resposta inválida do sistema de consulta. Tente novamente.'}

        # Salva o JSON integral no banco para cache futuro
        salvar_consulta(placa, json.dumps(dados_api))
        cooldowns_placa[ip_cliente] = time.time()
        await _resetar_falhas_modulo(request, 'placa')

        return {'sucesso': True, 'dados': dados_api, 'cache': False}

    except Exception as e:
        await _registrar_falha_modulo(request, 'placa')
        # 🛡️ Sanitiza a mensagem: exceções httpx podem conter a URL completa com o token na query string
        msg_erro = mascarar_tokens_em_texto(str(e))
        print(f'EXCEÇÃO INTERNA ROTA PLACA: {msg_erro}')
        return {'sucesso': False, 'erro': 'Erro interno no servidor. Tente novamente.'}
