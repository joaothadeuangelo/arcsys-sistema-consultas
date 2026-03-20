import os
import re
import json
import time
import logging

import httpx
from fastapi import APIRouter, Request

from database import is_manutencao, registrar_evento_telemetria_background, salvar_consulta
from .shared import (
    cooldown_comparador,
    mascarar_tokens_em_texto,
    obter_ip_real,
    verificar_turnstile,
)

router = APIRouter(prefix='/api')
logger = logging.getLogger(__name__)


@router.post('/comparar_facial')
async def comparar_facial(request: Request):
    # 1. Verifica se o sistema está em manutenção
    if is_manutencao():
        return {'sucesso': False, 'erro': '🛠️ MÓDULO EM MANUTENÇÃO!'}

    # 2. Puxa o IP do cliente (anti-spoofing)
    ip_cliente = obter_ip_real(request)

    # 🛡️ TRAVA DE COOLDOWN (RATE LIMIT DE 60 SEGUNDOS)
    tempo_atual = time.time()
    tempo_ultimo_uso = cooldown_comparador.get(ip_cliente, 0)
    tempo_restante = 60 - (tempo_atual - tempo_ultimo_uso)

    if tempo_restante > 0:
        return {'sucesso': False, 'erro': f'⏳ Aguarde {int(tempo_restante)} segundos para fazer uma nova comparação.'}

    # 3. Validação de Segurança do Turnstile
    token_turnstile = request.headers.get('X-Turnstile-Token')
    if not await verificar_turnstile(token_turnstile, ip_cliente):
        return {'sucesso': False, 'erro': '🤖 Bloqueado pela Segurança Cloudflare. Verifique se você é humano e tente novamente.'}

    registrar_evento_telemetria_background('uso_modulo', 'comparador', ip_cliente)

    # 4. Puxa a URL segura do arquivo .env
    url_destino = os.getenv('URL_MOTOR_FACIAL')
    if not url_destino:
        return {'sucesso': False, 'erro': 'URL do motor facial não configurada no servidor.'}

    try:
        # 5. Recebe os arquivos do frontend do ARCSYS
        form_data = await request.form()
        imagem_base = form_data.get('imagem_base')
        imagens_lote = form_data.getlist('imagens_lote')

        # 🛡️ VALIDAÇÃO BACK-END: Arquivos ausentes
        if not imagem_base or not imagens_lote:
            return {'sucesso': False, 'erro': 'Imagens ausentes. Envie a base e pelo menos uma imagem no lote.'}

        # 🛡️ VALIDAÇÃO BACK-END: Limite Máximo de 250 imagens
        if len(imagens_lote) > 250:
            return {'sucesso': False, 'erro': f'⚠️ Tentativa de abuso detectada! O limite máximo é de 250 imagens (Você enviou {len(imagens_lote)}).'}

        # 🛡️ VALIDAÇÃO BACK-END: Limite de 10MB por arquivo (Anti-OOM)
        TAMANHO_MAX_ARQUIVO = 10 * 1024 * 1024  # 10MB
        conteudo_base_preview = await imagem_base.read()
        if len(conteudo_base_preview) > TAMANHO_MAX_ARQUIVO:
            return {'sucesso': False, 'erro': '⚠️ A imagem base excede o limite de 10MB.'}
        # Rebobina o ponteiro do arquivo para leitura posterior
        await imagem_base.seek(0)

        # Atualiza o tempo do último uso deste IP (só bloqueia o tempo se passar das validações)
        cooldown_comparador[ip_cliente] = tempo_atual

        # 6. Prepara os arquivos com as ETIQUETAS EXATAS que o servidor parceiro exige
        files = []

        # 🎯 ETIQUETA CORRETA: base_file
        conteudo_base = await imagem_base.read()
        files.append(('base_file', (imagem_base.filename, conteudo_base, imagem_base.content_type)))

        # 🎯 ETIQUETA CORRETA: compare_files[]
        for img in imagens_lote:
            conteudo_lote = await img.read()
            files.append(('compare_files[]', (img.filename, conteudo_lote, img.content_type)))

        # 7. Faz o POST direto para o endpoint de processamento (compare.php)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url_destino, files=files)

            if response.status_code != 200:
                corpo_log = response.text[:500] if len(response.text) > 500 else response.text
                corpo_log = mascarar_tokens_em_texto(corpo_log)
                logger.warning('ERRO SIMILAR FACE STATUS: %s - BODY: %s', response.status_code, corpo_log)
                if ip_cliente in cooldown_comparador:
                    del cooldown_comparador[ip_cliente]
                return {'sucesso': False, 'erro': 'O servidor de biometria está temporariamente indisponível ou sobrecarregado. Tente novamente.'}

            # 8. Captura a resposta (que agora deve ser o JSON com a task_id)
            try:
                dados_retorno = response.json()
            except Exception:
                if ip_cliente in cooldown_comparador:
                    del cooldown_comparador[ip_cliente]
                return {'sucesso': False, 'erro': 'Resposta inválida do motor de biometria. Tente novamente.'}

            # 9. LOG DE USO: registra consultas do Similar Face no mesmo histórico dos outros módulos
            if response.status_code == 200:
                chave_log = f'SIMILAR_FACE_{ip_cliente}'
                try:
                    if isinstance(dados_retorno, (dict, list)):
                        payload_log = json.dumps(dados_retorno)
                        if len(payload_log) > 20000:
                            payload_log = json.dumps({
                                'status': 'Busca facial realizada',
                                'resumo': 'Payload extenso truncado para proteção de armazenamento.',
                                'tamanho_original': len(json.dumps(dados_retorno))
                            })
                    else:
                        payload_log = json.dumps({
                            'status': 'Busca facial realizada',
                            'resumo': str(dados_retorno)[:500]
                        })
                    salvar_consulta(chave_log, payload_log)
                except Exception as e:
                    # Falha de log não deve quebrar a resposta do usuário
                    logger.warning('FALHA AO REGISTRAR LOG SIMILAR FACE: %s', mascarar_tokens_em_texto(e))

            return {'sucesso': True, 'resultados': dados_retorno}

    # 🔒 BLINDAGEM MÁXIMA: Erros mascarados para não vazar IP/URL
    except Exception:
        # Se der erro no servidor, liberamos o IP para tentar de novo
        if ip_cliente in cooldown_comparador:
            del cooldown_comparador[ip_cliente]
        return {'sucesso': False, 'erro': 'O servidor de biometria está temporariamente indisponível ou sobrecarregado. Tente novamente.'}


@router.get('/comparar_facial/status/{task_id}')
async def checar_status_facial(task_id: str):
    if is_manutencao():
        return {'sucesso': False, 'erro': '🛠️ MÓDULO EM MANUTENÇÃO!'}

    url_destino = os.getenv('URL_MOTOR_FACIAL')
    if not url_destino:
        return {'sucesso': False, 'erro': 'URL do motor facial não configurada.'}

    # 🛡️ VALIDAÇÃO: Sanitiza o task_id para impedir SSRF e injeção de parâmetros na URL
    if not re.match(r'^[a-zA-Z0-9_-]{1,128}$', task_id):
        return {'sucesso': False, 'erro': 'ID de tarefa inválido.'}

    url_check = f'{url_destino}?task_id={task_id}&offset=0&limit=250'

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url_check)

            # Tenta ler a resposta como JSON
            try:
                dados_json = response.json()
            except Exception:
                return {'sucesso': True, 'concluido': False}  # Se não for JSON, ainda não tá pronto

            # 🎯 O VEREDITO: Lê a chave "task_status" que você encontrou na espionagem
            if dados_json.get('task_status') == 'SUCCESS':
                return {'sucesso': True, 'concluido': True, 'dados': dados_json}
            else:
                return {'sucesso': True, 'concluido': False}

    # 🔒 BLINDAGEM MÁXIMA: Erros mascarados para não vazar IP/URL
    except Exception:
        return {'sucesso': False, 'erro': 'Perda de conexão com o motor facial durante a verificação.'}
