import os
import time
import sqlite3
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from telethon import TelegramClient
from telethon.sessions import StringSession
from fastapi.staticfiles import StaticFiles

# ==========================================
# CONFIGURAÇÕES GERAIS E CREDENCIAIS
# ==========================================
load_dotenv()

API_ID = int(os.getenv('API_ID', 0))  
API_HASH = os.getenv('API_HASH', '')
BOT_USERNAME = os.getenv('BOT_USERNAME', '')
ADMIN_TOKEN = os.getenv('ADMIN_TOKEN', 'mudar_isso_depois')
AMBIENTE = os.getenv("AMBIENTE", "producao")

# Coleta todas as strings de sessão usando List Comprehension
SESSOES_STRINGS = [
    value.strip() for key, value in os.environ.items() 
    if key.startswith('SESSAO_') and value.strip()
]

# ==========================================
# ESTADO DA APLICAÇÃO E RATE LIMIT
# ==========================================
app = FastAPI(title="ARCYS - Consulta de Veículos")

# --- NOVA LINHA: ENSINA O SERVIDOR A LER CSS E JS ---
app.mount("/static", StaticFiles(directory="static"), name="static")

fila_clientes = asyncio.Queue()

cooldowns_por_ip = {}
TEMPO_COOLDOWN = 60 # Tempo de espera em segundos



# ==========================================
# CONFIGURAÇÃO DO BANCO DE DADOS
# ==========================================
DB_PATH = '/data/consultas.db' if os.path.exists('/data') else 'consultas.db'

def iniciar_banco() -> None:
    """Cria as tabelas de registros e configurações caso não existam."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Tabela de Histórico de Placas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registro_placas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            dados TEXT NOT NULL,
            data_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela do Botão de Pânico (Configurações do Sistema)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    ''')
    
    # Garante que o sistema nasce "Ligado" (0 = Sem manutenção)
    cursor.execute("INSERT OR IGNORE INTO configuracoes (chave, valor) VALUES ('manutencao', '0')")
    
    conn.commit()
    conn.close()

def salvar_consulta(placa: str, dados: str) -> None:
    """Salva o resultado de uma consulta no banco."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO registro_placas (placa, dados) VALUES (?, ?)', (placa, dados))
    conn.commit()
    conn.close()

def buscar_consulta(placa: str):
    """Verifica se uma placa já foi consultada recentemente."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT dados FROM registro_placas WHERE placa = ? ORDER BY data_consulta DESC LIMIT 1', (placa,))
    resultado = cursor.fetchone()
    conn.close()
    
    return resultado[0] if resultado else None

def deletar_consulta_bugada(placa: str):
    """Deleta do banco caso tenha salvo a mensagem temporária por engano."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM registro_placas WHERE placa = ? AND dados LIKE '%Consultando%'", (placa,))
    conn.commit()
    conn.close()

# --- FUNÇÕES DO MODO MANUTENÇÃO ---
def is_manutencao() -> bool:
    """Verifica se o botão de pânico (manutenção) está ativado no banco"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT valor FROM configuracoes WHERE chave = 'manutencao'")
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] == '1' if resultado else False

def toggle_manutencao() -> None:
    """Inverte o status do sistema (Liga/Desliga)"""
    atual = is_manutencao()
    novo_valor = '0' if atual else '1' # Se estava 1, vira 0. Se estava 0, vira 1.
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE configuracoes SET valor = ? WHERE chave = 'manutencao'", (novo_valor,))
    conn.commit()
    conn.close()

# ==========================================
# EVENTOS DE INICIALIZAÇÃO
# ==========================================
@app.on_event("startup")
async def startup_event():
    iniciar_banco()
    print(f"Iniciando {len(SESSOES_STRINGS)} contas do Telegram via StringSession...")
    
    for idx, session_str in enumerate(SESSOES_STRINGS):
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.start()
            await fila_clientes.put(client)
            print(f"✅ Conta {idx + 1} conectada e pronta na fila!")
        except Exception as e:
            print(f"❌ Erro ao conectar a conta {idx + 1}: {e}")
            
    print("🚀 Todas as contas operacionais!")

# ==========================================
# ROTAS DA APLICAÇÃO (ENDPOINTS)
# ==========================================
@app.get("/", response_class=HTMLResponse)
async def serve_html():
    """Renderiza a página inicial (Frontend) e injeta o status de manutenção."""
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
        
    # Verifica o status atual no banco
    status_manutencao = "true" if is_manutencao() else "false"
    
    # Injeta a variável JavaScript invisível no <head> da página do usuário
    script_injetado = f"<script>window.SISTEMA_EM_MANUTENCAO = {status_manutencao};</script>\n</head>"
    html = html.replace("</head>", script_injetado)
    
    return html

@app.get("/api/consultar/{placa}")
async def consultar_placa(placa: str, request: Request):
    """Endpoint principal de consulta de placas."""
    
    # 1. BLOQUEIO DE SEGURANÇA BACKEND (Caso tentem burlar o frontend)
    if is_manutencao():
        return {
            "sucesso": False, 
            "dados": "🛠️ **SISTEMA EM MANUTENÇÃO!**\n\nNossos engenheiros tropeçaram nos cabos do servidor. Estamos arrumando a bagunça. Tente novamente mais tarde."
        }
        
    placa = placa.upper()
    
    # Extração de IP considerando proxies de nuvem (Railway)
    ip_cliente = request.headers.get("X-Forwarded-For", request.client.host)
    if ip_cliente:
        ip_cliente = ip_cliente.split(",")[0].strip()
        
    tempo_atual = time.time()
    ultimo_tempo = cooldowns_por_ip.get(ip_cliente, 0)
    
    try:
        # Limpa lixo do banco (caso você pesquise a mesma placa que travou antes)
        deletar_consulta_bugada(placa)

        # Verifica Cache (Banco de Dados)
        dados_salvos = buscar_consulta(placa)
        if dados_salvos:
            return {"sucesso": True, "dados": dados_salvos, "cache": True}

        # Verificação de Cooldown (Rate Limit por IP)
        tempo_passado = tempo_atual - ultimo_tempo
        if tempo_passado < TEMPO_COOLDOWN:
            tempo_restante = int(TEMPO_COOLDOWN - tempo_passado)
            return {
                "sucesso": False, 
                "dados": f"🚨 Calma lá, apressadinho! O sistema é de graça.\nAguarde mais {tempo_restante} segundos para fazer uma nova consulta no bot."
            }

        # =======================================================
        # 🚧 MODO DE DESENVOLVIMENTO (MOCK / SIMULAÇÃO)
        # =======================================================
        if AMBIENTE == "desenvolvimento":
            print(f"⚠️ [DEV MODE] Simulando consulta local para a placa {placa} sem usar o Telegram...")
            
            await asyncio.sleep(2) # Simula o tempinho de carregamento das zoeiras
            
            # Resposta falsa (Coloquei Roubo: SIM para você testar a etiqueta vermelha piscando!)
            resposta_mock = f"""🕵️ **CONSULTA DE PLACA COMPLETA** 🕵️

• **DADOS PRINCIPAIS**

• **Placa:** `{placa}`
• **Chassi:** `3KPFN414BKE278951`
• **RENAVAM:** `01169511870`
• **Situação:** `EM_CIRCULACAO`

• **RESTRIÇÕES / ALERTAS**

• **Restrição 1:** `SEM RESTRICAO`
• **Roubo / Furto:** `SIM`

• DATAS E SERVIÇOS

• **Serviço Consultado:** `RENAVAM_MOCK_LOCAL_ARCSYS`"""

            # Salva no banco local e seta o cooldown para testarmos o fluxo completo no frontend
            salvar_consulta(placa, resposta_mock)
            cooldowns_por_ip[ip_cliente] = time.time()
            
            return {"sucesso": True, "dados": resposta_mock, "cache": False}
        # =======================================================

        # Processamento via Telegram (Fila) -> SÓ RODA EM PRODUÇÃO
        cliente_atual = await fila_clientes.get()
        
        try:
            # Health Check da Conexão
            if not cliente_atual.is_connected():
                print("⚠️ Conta desconectada detectada. Forçando reconexão...")
                await cliente_atual.connect()
            
            # Envia o comando
            await cliente_atual.send_message(BOT_USERNAME, f'/placa {placa}')
            
            # LOOP INTELIGENTE DE ESPERA (Máximo de 30 segundos)
            resposta_final = None
            for tentativa in range(15):
                await asyncio.sleep(2) # Verifica de 2 em 2 segundos
                messages = await cliente_atual.get_messages(BOT_USERNAME, limit=1)
                
                if messages and messages[0].text:
                    texto = messages[0].text
                    
                    if texto.startswith('/placa'):
                        continue
                    if "Consultando..." in texto or "Processando sua solicitação" in texto:
                        continue
                        
                    resposta_final = texto
                    break
            
            if resposta_final:
                # Tratamento da resposta (Remoção de rodapé do bot original)
                if "👤 Usuário:" in resposta_final:
                    resposta_final = resposta_final.split("👤 Usuário:")[0].strip()
                
                # FILTRO ANTI-FANTASMA (Intercepta erros do bot original)
                if "Placa inválida" in resposta_final or "não encontrada" in resposta_final.lower() or "inexistente" in resposta_final.lower():
                    return {
                        "sucesso": False, 
                        "dados": "🐴 **DIGITA ESSA PLACA DIREITO, ANIMAL!**\n\nEssa placa não existe nem no sistema do Detran e nem no ferro-velho. Vê se não digitou a placa do seu carrinho de rolimã!"
                    }
                
                elif "Não foi possível realizar a consulta" in resposta_final or "GonzalesCanal" in resposta_final:
                    return {
                        "sucesso": False, 
                        "dados": "🔥 **SISTEMA DE RESSACA!**\n\nO servidor central deu uma capotada ou está em manutenção. Vá tomar uma água e tente de novo daqui a pouco (e não adianta ficar dando F5 como um desesperado)."
                    }

                # Só salva no banco se for uma consulta de sucesso real!
                salvar_consulta(placa, resposta_final)
                cooldowns_por_ip[ip_cliente] = time.time()
                
                return {"sucesso": True, "dados": resposta_final, "cache": False}
            else:
                return {"sucesso": False, "dados": "O bot oficial demorou muito para responder (Time-out). Tente novamente."}
                
        finally:
            # Garante que a conta retorne para a fila mesmo em caso de erro
            await fila_clientes.put(cliente_atual)
            
    except Exception as e:
        return {
            "sucesso": False, 
            "dados": f"Erro interno de conexão: {str(e)}\nTente novamente em alguns segundos."
        }

# ==========================================
# ROTAS DO DASHBOARD ADMIN E CONTROLES
# ==========================================

@app.get("/admin/toggle")
async def alternar_status(token: str):
    """Rota invisível que inverte o status de manutenção e redireciona de volta."""
    if token != ADMIN_TOKEN:
        return "<h1>Acesso Negado</h1>"
    
    toggle_manutencao()
    return RedirectResponse(url=f"/admin/lista?token={token}")

@app.get("/admin/lista", response_class=HTMLResponse)
async def ver_historico(token: str):
    """Painel de administração para visualização dos registros no banco e botão de pânico."""
    if token != ADMIN_TOKEN:
        return "<h1>Acesso Negado, amigão!</h1>"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT placa, dados, data_consulta FROM registro_placas ORDER BY data_consulta DESC LIMIT 100')
    rows = cursor.fetchall()
    conn.close()

    # Define o visual do painel baseado no status atual do sistema
    status_atual = is_manutencao()
    cor_borda = "#e74c3c" if status_atual else "#2ecc71"
    status_texto = "EM MANUTENÇÃO (SISTEMA DESLIGADO)" if status_atual else "ONLINE (SISTEMA RODANDO)"
    btn_texto = "🟢 LIGAR SISTEMA" if status_atual else "🔴 DESLIGAR SISTEMA (MANUTENÇÃO)"
    btn_cor = "#27ae60" if status_atual else "#c0392b"

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard ARCYS</title>
        <style>
            .celula-dados {{
                max-width: 400px; max-height: 150px; overflow-y: auto;
                background: #0e1621; padding: 10px; border-radius: 6px;
                font-size: 0.85em; white-space: pre-wrap; color: #a1c181;
                border-left: 3px solid #5288c1;
            }}
            .celula-dados::-webkit-scrollbar {{ width: 6px; }}
            .celula-dados::-webkit-scrollbar-thumb {{ background: #5288c1; border-radius: 4px; }}
            
            .painel-controle {{
                background: #17212b; padding: 20px; border-radius: 8px; margin-bottom: 30px; 
                display: flex; justify-content: space-between; align-items: center;
                border-left: 6px solid {cor_borda}; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }}
            .btn-power {{
                background-color: {btn_cor}; color: white; padding: 12px 24px; text-decoration: none; 
                border-radius: 6px; font-weight: bold; transition: 0.2s; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }}
            .btn-power:hover {{ filter: brightness(1.2); transform: translateY(-2px); }}
        </style>
    </head>
    <body style="background:#0e1621; color:white; font-family:sans-serif; padding:40px;">
        
        <div class="painel-controle">
            <div>
                <h2 style="margin: 0; color: #fff;">Painel de Controle ARCYS</h2>
                <p style="margin: 5px 0 0 0; color: {cor_borda}; font-weight: bold;">Status Atual: {status_texto}</p>
            </div>
            <a href="/admin/toggle?token={token}" class="btn-power">{btn_texto}</a>
        </div>

        <h2>📊 Relatório de Consultas - ARCYS</h2>
        <table border="1" style="width:100%; border-collapse:collapse; background:#17212b; border-color: #242f3d;">
            <tr style="background:#5288c1;">
                <th style="padding:15px; width: 10%;">Placa</th>
                <th style="padding:15px; width: 70%;">Dados Retornados</th>
                <th style="padding:15px; width: 20%;">Data/Hora (UTC)</th>
            </tr>
    """
    for row in rows:
        placa = row[0]
        dados = row[1]
        data = row[2]
        
        html += f"""
            <tr>
                <td style='padding:15px; text-align:center; font-weight:bold; vertical-align:top;'>{placa}</td>
                <td style='padding:15px; vertical-align:top;'>
                    <div class="celula-dados">{dados}</div>
                </td>
                <td style='padding:15px; text-align:center; color:#8aa3ba; vertical-align:top;'>{data}</td>
            </tr>
        """
    
    html += """
        </table>
    </body>
    </html>
    """
    return html