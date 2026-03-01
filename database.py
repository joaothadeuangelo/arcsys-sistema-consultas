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
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao', '0')")
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