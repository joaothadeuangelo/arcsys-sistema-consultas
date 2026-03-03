import os
import sqlite3

DB_PATH = '/data/consultas.db' if os.path.exists('/data') else 'consultas.db'

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
    
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_placa', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_cnh', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_cpf', '0')")
    
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
    cursor.execute('SELECT placa, dados, data_consulta FROM registro_placas ORDER BY data_consulta DESC LIMIT ? OFFSET ?', (limite, offset))
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