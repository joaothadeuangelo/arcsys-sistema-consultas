# ARCSYS - Sistema de Consultas e Telemetria

## Descricao
O ARCSYS e uma aplicacao web desenvolvida para centralizar consultas de dados em modulos especializados, com painel administrativo protegido, integracao com APIs externas e camada de telemetria operacional.

O sistema combina:
- Painel administrativo com controle de operacao e monitoramento.
- Modulos de consulta (placa, CNH, CPF, nome e comparador) conectados a servicos externos.
- Cache de consultas em SQLite para reduzir latencia e chamadas repetidas.
- Interface premium com experiencia visual em modo escuro.

## Stack Tecnologico
- Python
- FastAPI
- SQLite
- Jinja2
- HTML/CSS Vanilla

## Features de Seguranca
- Protecao de rotas administrativas com token e cookie seguro.
- Cloudflare Turnstile para mitigacao de abuso automatizado.
- Hardening de IP com validacao de origem e controles de uso.
- Kill Switch / Graceful Shutdown para encerramento automatico e seguro da operacao.

## Como Rodar Localmente
1. Crie e ative um ambiente virtual (opcional, recomendado).
2. Instale as dependencias:

```bash
pip install -r requirements.txt
```

3. Crie o arquivo .env com base no .env.example e preencha as variaveis.
4. Inicie a aplicacao:

```bash
uvicorn main:app --reload
```

5. Acesse no navegador:
- http://127.0.0.1:8000

## Estrutura Geral
- main.py: inicializacao da aplicacao, middlewares e roteadores.
- database.py: conexao SQLite, schema e operacoes de cache/telemetria.
- routers/: endpoints por modulo e area administrativa.
- templates/ e static/: camada visual (Jinja2, CSS e JS).

## Observacoes
Este repositorio foi preparado para portfolio com foco em arquitetura, seguranca e operacao. Segredos, bancos locais e artefatos de ambiente estao bloqueados no .gitignore.
