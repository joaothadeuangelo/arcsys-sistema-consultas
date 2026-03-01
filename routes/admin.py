import os
import sqlite3
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from database import DB_PATH, is_manutencao, toggle_manutencao

router = APIRouter()
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'mudar_isso_depois')

@router.get("/admin/toggle")
async def alternar_status(token: str):
    if token != ADMIN_TOKEN: return "<h1>Acesso Negado</h1>"
    toggle_manutencao()
    return RedirectResponse(url=f"/admin/lista?token={token}")

@router.get("/admin/lista", response_class=HTMLResponse)
async def ver_historico(token: str):
    if token != ADMIN_TOKEN: return "<h1>Acesso Negado</h1>"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT placa, dados, data_consulta FROM registro_placas ORDER BY data_consulta DESC LIMIT 100')
    rows = cursor.fetchall()
    conn.close()

    status_atual = is_manutencao()
    cor_borda = "#e74c3c" if status_atual else "#2ecc71"
    status_texto = "EM MANUTENÇÃO" if status_atual else "ONLINE"
    btn_texto = "LIGAR SISTEMA" if status_atual else "DESLIGAR SISTEMA"
    btn_cor = "#27ae60" if status_atual else "#c0392b"

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Dashboard ARCSYS</title>
        <style>
            body {{ background:#0e1621; color:white; font-family:sans-serif; padding:40px; }}
            .celula-dados {{ max-width: 400px; max-height: 150px; overflow-y: auto; background: #17212b; padding: 10px; font-size: 0.85em; white-space: pre-wrap; border-left: 3px solid #5288c1; }}
            .painel-controle {{ background: #17212b; padding: 20px; border-radius: 8px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: center; border-left: 6px solid {cor_borda}; }}
            .btn-power {{ background-color: {btn_cor}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="painel-controle">
            <div><h2 style="margin: 0;">Painel de Controle</h2><p style="color: {cor_borda};">Status: {status_texto}</p></div>
            <a href="/admin/toggle?token={token}" class="btn-power">{btn_texto}</a>
        </div>
        <h2>📊 Relatório de Consultas</h2>
        <table border="1" style="width:100%; border-collapse:collapse; border-color: #242f3d;">
            <tr style="background:#5288c1;"><th style="padding:15px;">Chave</th><th style="padding:15px;">Dados</th><th style="padding:15px;">Data</th></tr>
    """
    for row in rows:
        html += f"<tr><td style='padding:15px; text-align:center;'>{row[0]}</td><td style='padding:15px;'><div class='celula-dados'>{row[1]}</div></td><td style='padding:15px; text-align:center;'>{row[2]}</td></tr>"
    
    html += "</table></body></html>"
    return html