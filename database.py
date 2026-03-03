import os
import sqlite3

DB_PATH = '/data/consultas.db' if os.path.exists('/data') else 'consultas.db'

def iniciar_banco() -> None:
    conn = sqlite3.connect(DB_PATH)
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
    
    # Inserindo o Botão Global (Botão do Pânico)
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao', '0')")
    
    # Inserindo as chaves individuais dos módulos (Padrão: 0 = Ligado/Operacional)
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_placa', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_cnh', '0')")
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao_cpf', '0')")
    
    conn.commit()
    conn.close()

def salvar_consulta(chave_busca: str, dados: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO registro_placas (placa, dados) VALUES (?, ?)', (chave_busca, dados))
    conn.commit()
    conn.close()

def buscar_consulta(chave_busca: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT dados FROM registro_placas WHERE placa = ? ORDER BY data_consulta DESC LIMIT 1', (chave_busca,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None

# ==========================================
# FUNÇÕES GLOBAIS (O BOTÃO DO PÂNICO)
# ==========================================
def is_manutencao() -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'manutencao'")
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] == '1' if resultado else False

def toggle_manutencao() -> None:
    atual = is_manutencao()
    novo_valor = '0' if atual else '1'
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracoes SET valor = ? WHERE chave = 'manutencao'", (novo_valor,))
    conn.commit()
    conn.close()

# ==========================================
# FUNÇÕES MODULARES (CONTROLE INDEPENDENTE)
# ==========================================
def is_manutencao_modulo(modulo: str) -> bool:
    """Verifica se um módulo específico (placa, cnh, cpf) está em manutenção."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM configuracoes WHERE chave = ?", (f'manutencao_{modulo}',))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] == '1' if resultado else False

def toggle_manutencao_modulo(modulo: str) -> None:
    """Liga ou desliga um módulo específico."""
    atual = is_manutencao_modulo(modulo)
    novo_valor = '0' if atual else '1'
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracoes SET valor = ? WHERE chave = ?", (novo_valor, f'manutencao_{modulo}'))
    conn.commit()
    conn.close()

def get_status_todos_modulos() -> dict:
    """Retorna um dicionário com o status de todos os módulos para o painel de Admin."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT chave, valor FROM configuracoes")
    resultados = cursor.fetchall()
    conn.close()
    
    # Converte os resultados ('0' ou '1') em booleanos (False ou True)
    status = {linha[0]: linha[1] == '1' for linha in resultados}
    return status