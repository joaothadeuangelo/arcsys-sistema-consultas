import os
import sqlite3
import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DB_PATH = '/data/consultas.db' if os.path.exists('/data') else 'consultas.db'
TELEMETRIA_SALT = os.getenv('TELEMETRIA_SALT', 'arcsys-telemetria-salt')
TZ_BRASIL = ZoneInfo('America/Sao_Paulo')

# ==========================================
# CONEXÃO BLINDADA (O Segredo para não perder dados)
# ==========================================
def obter_conexao():
    # timeout=20: Se o banco estiver ocupado, espera na fila em vez de dar erro
    conn = sqlite3.connect(DB_PATH, timeout=20)
    # Ativa o modo WAL (Alta concorrência para leitura/escrita simultânea)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def iniciar_banco() -> None:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registro_placas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            dados TEXT NOT NULL,
            data_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tipo_evento TEXT NOT NULL,
            detalhe TEXT NOT NULL,
            ip_hash TEXT
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_telemetria_data_tipo ON telemetria(data_hora, tipo_evento)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_telemetria_tipo_detalhe ON telemetria(tipo_evento, detalhe)')
    
    # 🎯 INJEÇÃO DAS CHAVES DE MANUTENÇÃO (Incluindo o novo Comparador)
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_placa', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_cnh', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_cpf', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_nome', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_comparador', '0')")
    
    conn.commit()
    conn.close()

# ==========================================
# FUNÇÕES DE CACHE E LOG
# ==========================================
def salvar_consulta(chave_busca: str, dados: str) -> None:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO registro_placas (placa, dados) VALUES (?, ?)', (chave_busca, dados))
    conn.commit()
    conn.close()

def buscar_consulta(chave_busca: str):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute('SELECT dados FROM registro_placas WHERE placa = ? ORDER BY data_consulta DESC LIMIT 1', (chave_busca,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None

# ==========================================
# NOVAS FUNÇÕES: CONTADOR E PAGINAÇÃO (ADMIN)
# ==========================================
def contar_total_consultas() -> int:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM registro_placas")
    total = cursor.fetchone()[0]
    conn.close()
    return total

def obter_historico_paginado(limite: int, offset: int):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            placa,
            dados,
            datetime(data_consulta, '-3 hours') AS data_consulta_br
        FROM registro_placas
        ORDER BY data_consulta DESC
        LIMIT ? OFFSET ?
    ''', (limite, offset))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ==========================================
# FUNÇÕES DE SISTEMA (ON/OFF)
# ==========================================
def is_manutencao() -> bool:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'manutencao'")
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] == '1' if resultado else False

def toggle_manutencao() -> None:
    atual = is_manutencao()
    novo_valor = '0' if atual else '1'
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracoes SET valor = ? WHERE chave = 'manutencao'", (novo_valor,))
    conn.commit()
    conn.close()

def is_manutencao_modulo(modulo: str) -> bool:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM configuracoes WHERE chave = ?", (f'manutencao_{modulo}',))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] == '1' if resultado else False

def toggle_manutencao_modulo(modulo: str) -> None:
    atual = is_manutencao_modulo(modulo)
    novo_valor = '0' if atual else '1'
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracoes SET valor = ? WHERE chave = ?", (novo_valor, f'manutencao_{modulo}'))
    conn.commit()
    conn.close()

def get_status_todos_modulos() -> dict:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT chave, valor FROM configuracoes")
    resultados = cursor.fetchall()
    conn.close()
    return {linha[0]: linha[1] == '1' for linha in resultados}


# ==========================================
# TELEMETRIA (ANALYTICS INTERNO)
# ==========================================
def gerar_ip_hash(ip_ou_id: str) -> str:
    if not ip_ou_id:
        ip_ou_id = 'anonimo'
    base = f'{TELEMETRIA_SALT}:{ip_ou_id}'
    return hashlib.sha256(base.encode('utf-8')).hexdigest()


def _registrar_evento_telemetria_sync(tipo_evento: str, detalhe: str, ip_hash: str) -> None:
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO telemetria (tipo_evento, detalhe, ip_hash) VALUES (?, ?, ?)',
        (tipo_evento, detalhe, ip_hash)
    )
    conn.commit()
    conn.close()


async def registrar_evento_telemetria(tipo_evento: str, detalhe: str, ip_ou_id: str) -> None:
    ip_hash = gerar_ip_hash(ip_ou_id)
    await asyncio.to_thread(_registrar_evento_telemetria_sync, tipo_evento, detalhe, ip_hash)


def registrar_evento_telemetria_background(tipo_evento: str, detalhe: str, ip_ou_id: str) -> None:
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(registrar_evento_telemetria(tipo_evento, detalhe, ip_ou_id))
    except RuntimeError:
        try:
            ip_hash = gerar_ip_hash(ip_ou_id)
            _registrar_evento_telemetria_sync(tipo_evento, detalhe, ip_hash)
        except Exception:
            pass


def obter_resumo_telemetria_hoje() -> dict:
    conn = obter_conexao()
    cursor = conn.cursor()

    agora_sp = datetime.now(TZ_BRASIL)
    inicio_dia_sp = datetime.combine(agora_sp.date(), datetime.min.time(), tzinfo=TZ_BRASIL)
    fim_dia_sp = inicio_dia_sp + timedelta(days=1)

    inicio_utc = inicio_dia_sp.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    fim_utc = fim_dia_sp.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute('''
        SELECT COUNT(DISTINCT ip_hash)
        FROM telemetria
        WHERE tipo_evento = 'page_view'
          AND detalhe = 'home'
          AND data_hora >= ?
          AND data_hora < ?
    ''', (inicio_utc, fim_utc))
    total_visitas_unicas = cursor.fetchone()[0] or 0

    cursor.execute('''
        SELECT detalhe, COUNT(*)
        FROM telemetria
        WHERE tipo_evento = 'uso_modulo'
          AND data_hora >= ?
          AND data_hora < ?
        GROUP BY detalhe
        ORDER BY COUNT(*) DESC
    ''', (inicio_utc, fim_utc))
    uso_modulos = {detalhe: total for detalhe, total in cursor.fetchall()}

    conn.close()
    return {
        'data': agora_sp.strftime('%d/%m/%Y'),
        'timezone': 'America/Sao_Paulo',
        'total_visitas_unicas': total_visitas_unicas,
        'uso_modulos': uso_modulos
    }