import os
import hmac

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix='/api/admin')

ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', '')
COOKIE_ADMIN = 'admin_session'


def token_admin_valido(token: str) -> bool:
    if not ADMIN_TOKEN:
        return False
    if not token:
        return False
    return hmac.compare_digest(token, ADMIN_TOKEN)


def admin_autenticado(request: Request) -> bool:
    token_cookie = request.cookies.get(COOKIE_ADMIN, '')
    return token_admin_valido(token_cookie)


@router.get('/status-circuit-breaker')
async def status_circuit_breaker(request: Request):
    """Endpoint leve de monitoramento do contador de falhas consecutivas."""
    if not admin_autenticado(request):
        return JSONResponse({'erro': 'Acesso negado.'}, status_code=403)

    estado = getattr(request.app.state, 'falhas_consecutivas', {})

    # Resposta mínima: expõe apenas os contadores dos módulos monitorados.
    placa = int(estado.get('placa', 0)) if isinstance(estado, dict) else 0
    cnh = int(estado.get('cnh', 0)) if isinstance(estado, dict) else 0
    fotocnhsp = int(estado.get('fotocnhsp', 0)) if isinstance(estado, dict) else 0

    return {'placa': placa, 'cnh': cnh, 'fotocnhsp': fotocnhsp}
