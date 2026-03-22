import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Carrega seu API_ID e API_HASH do arquivo .env atual
load_dotenv()
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

def gerar_sessao() -> str:
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        return client.session.save()


def salvar_sessao_em_arquivo(sessao: str) -> None:
    caminho_saida = os.getenv('SESSAO_OUTPUT_FILE', 'sessao_gerada.txt')
    with open(caminho_saida, 'w', encoding='utf-8') as arquivo:
        arquivo.write(sessao)


if __name__ == '__main__':
    sessao = gerar_sessao()
    salvar_sessao_em_arquivo(sessao)