from fastapi import APIRouter, Request

router = APIRouter(prefix='/api/admin')


@router.get('/status-circuit-breaker')
async def status_circuit_breaker(request: Request):
    """Endpoint leve de monitoramento do contador de falhas consecutivas."""
    estado = getattr(request.app.state, 'falhas_consecutivas', {})

    # Resposta mínima: expõe apenas os contadores dos módulos monitorados.
    placa = int(estado.get('placa', 0)) if isinstance(estado, dict) else 0
    cnh = int(estado.get('cnh', 0)) if isinstance(estado, dict) else 0

    return {'placa': placa, 'cnh': cnh}
