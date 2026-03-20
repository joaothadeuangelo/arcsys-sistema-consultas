import os
import time
import base64

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from database import is_manutencao, is_manutencao_modulo, registrar_evento_telemetria_background, salvar_consulta
from .shared import cooldowns_fotocnhsp, obter_ip_real, verificar_cooldown_ip, verificar_turnstile, _registrar_falha_modulo, _resetar_falhas_modulo

URL_API_FOTO_CNH_SP = os.getenv('URL_API_FOTO_CNH_SP', '')

router = APIRouter(prefix='/api')


async def _resposta_erro(request: Request, ip_cliente: str, status_code: int, mensagem: str):
    registrar_evento_telemetria_background('erro_modulo', 'fotocnhsp', ip_cliente)
    await _registrar_falha_modulo(request, 'fotocnhsp')
    return JSONResponse({'erro': mensagem}, status_code=status_code)


@router.get('/consultar_fotocnhsp/{cpf}')
async def consultar_fotocnhsp(cpf: str, request: Request):
    ip_cliente = obter_ip_real(request)

    if is_manutencao() or is_manutencao_modulo('fotocnhsp'):
        return await _resposta_erro(request, ip_cliente, 503, 'Foto não encontrada ou indisponível no momento.')

    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    if len(cpf_limpo) != 11:
        return await _resposta_erro(request, ip_cliente, 400, 'CPF inválido. Digite os 11 números corretamente.')

    token_turnstile = request.headers.get('X-Turnstile-Token')
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return await _resposta_erro(request, ip_cliente, 403, '🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente.')

    permitido, restante = verificar_cooldown_ip(ip_cliente, cooldowns_fotocnhsp, 120)
    if not permitido:
        return JSONResponse({'erro': f'Aguarde {restante} segundos para consultar novamente.'}, status_code=429)

    registrar_evento_telemetria_background('uso_modulo', 'fotocnhsp', ip_cliente)

    if not URL_API_FOTO_CNH_SP:
        return await _resposta_erro(request, ip_cliente, 503, 'Foto não encontrada ou indisponível no momento.')

    try:
        url = f"{URL_API_FOTO_CNH_SP}{cpf_limpo}"
        timeout = httpx.Timeout(15.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resposta = await client.get(url)
            resposta.raise_for_status()
            payload = resposta.json()

        if payload.get('erro') is not False:
            return await _resposta_erro(request, ip_cliente, 404, 'Foto não encontrada ou indisponível no momento.')

        foto_b64 = payload.get('foto')
        if not foto_b64:
            return await _resposta_erro(request, ip_cliente, 404, 'Foto não encontrada ou indisponível no momento.')

        if ',' in foto_b64:
            foto_b64 = foto_b64.split(',', 1)[1]

        try:
            image_bytes = base64.b64decode(foto_b64, validate=True)
        except Exception:
            return await _resposta_erro(request, ip_cliente, 400, 'Foto não encontrada ou indisponível no momento.')

        cooldowns_fotocnhsp[ip_cliente] = time.time()
        salvar_consulta(f'FOTOCNHSP_{cpf_limpo}', 'FOTO CNH SP: consulta concluida com sucesso')
        await _resetar_falhas_modulo(request, 'fotocnhsp')
        return Response(content=image_bytes, media_type='image/jpeg')

    except httpx.TimeoutException:
        return await _resposta_erro(request, ip_cliente, 504, 'Foto não encontrada ou indisponível no momento.')
    except (httpx.HTTPError, ValueError):
        return await _resposta_erro(request, ip_cliente, 400, 'Foto não encontrada ou indisponível no momento.')
    except Exception:
        return await _resposta_erro(request, ip_cliente, 500, 'Foto não encontrada ou indisponível no momento.')
