import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Carrega seu API_ID e API_HASH do arquivo .env atual
load_dotenv()
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

print("=== GERADOR DE SESSÃO DO TELEGRAM ===")
print("Deixe o seu celular com o Telegram aberto em mãos.\n")

# O StringSession() vazio indica que queremos criar um novo login
with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\n✅ LOGIN BEM SUCEDIDO!\n")
    print("👇 COPIE O TEXTO GIGANTE ABAIXO E GUARDE COM CUIDADO 👇\n")
    
    # Isso aqui imprime a string gigante que é o seu "arquivo" de login
    print(client.session.save())
    
    print("\n👆 COPIE O TEXTO GIGANTE ACIMA 👆")
    print("ATENÇÃO: Quem tiver esse texto tem acesso à sua conta. Não compartilhe!")