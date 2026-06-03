# %% [markdown]
# # Painel Interativo de Exploração de Dados - DEX
# Este painel permite que você decida se quer puxar dados em tempo real ou ler o que já foi enviado ao banco.

# %%
import sys
from pathlib import Path

# PEP 8: Adiciona dinamicamente a pasta raiz do projeto ao path de importações do Python
DIRETORIO_RAIZ = Path(__file__).resolve().parents[1]
if str(DIRETORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRETORIO_RAIZ))

import asyncio
import pandas as pd

# Importa com segurança as funções localizadas na raiz do projeto
from main import obter_dados_em_memoria, obter_dados_carregados_em_memoria

# Bases que você deseja analisar na sessão de hoje
bases_alvo = ["orcado", "fatofechamento"]

# %% [markdown]
## Opção A: Puxar do OLAP/Origem e Transformar (Sem Carga)
## Execute esta célula se quiser ver modificações de código feitas nas regras do Transform agora.

# %%
##print("Extraindo e Transformando dados das origens... Aguarde...")
##dados_estudo = asyncio.run(obter_dados_em_memoria(bases_alvo))
##print(f"\nTabelas prontas para estudo (Tempo de Execução): {list(dados_estudo.keys())}")

# %% [markdown]
# ### Opção B: Consultar DIRETAMENTE do banco de dados (LOAD)
# Execute esta célula se quiser analisar os dados exatamente da forma que eles foram gravados no banco de dados FINANCA (`dbo.dex-*`).
# Muito mais rápido, pois pula a busca no OLAP.

# %%
print("Consultando tabelas 'dbo.dex-*' no SQL Server (FINANCA)...")
dados_estudo = asyncio.run(obter_dados_carregados_em_memoria(bases_alvo))
print(f"\nTabelas lidas diretamente da Carga: {list(dados_estudo.keys())}")

# %% [markdown]
# ---
# ### Espaço para Exploração Livre (Consome as tabelas independente da Opção escolhida acima)

# %%
if "fatofechamento" in dados_estudo:
    df_fatos = dados_estudo["fatofechamento"]
    print(f"Volume de registros lidos do fatofechamento: {len(df_fatos)}")
    display(df_fatos.head())

# %%
if "orcado_receitas" in dados_estudo:
    df_orcado = dados_estudo["orcado_receitas"]
    print(f"Volume de registros lidos do orcado_receitas: {len(df_orcado)}")
    display(df_orcado.head())

# %% [markdown]
# ### Agrupamento Analítico de Teste

# %%
# Se os dados existirem, você pode validar o somatório
if "fatofechamento" in dados_estudo:
    df_fatos = dados_estudo["fatofechamento"]
    if "nm_cc" in df_fatos.columns and "vl_valor" in df_fatos.columns:
        resumo = df_fatos.groupby("nm_cc")["vl_valor"].sum().reset_index()
        display(resumo.sort_values(by="vl_valor", ascending=False).head(10))
