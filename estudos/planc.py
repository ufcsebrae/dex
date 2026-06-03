# %% [markdown]
# # Painel Interativo de Estudos com Cache Local (DEX)
# Este painel utiliza um banco de dados SQLite local (`data/cache.db`) para acelerar as consultas
# e economizar conexões de rede com os bancos de dados remotos.

# %%
import sys
import sqlite3
from pathlib import Path

from sqlalchemy import false

# PEP 8: Adiciona o diretório raiz ao path de busca do Python para permitir importações
DIRETORIO_RAIZ = Path(__file__).resolve().parents[1]
if str(DIRETORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRETORIO_RAIZ))

import asyncio
import pandas as pd

# Importa o orquestrador para busca remota se o cache estiver vazio
from main import obter_dados_carregados_em_memoria

# Configuração física do cache (PEP 8)
CAMINHO_PASTA_DATA = DIRETORIO_RAIZ / "data"
CAMINHO_PASTA_DATA.mkdir(parents=True, exist_ok=True)  # Garante que a pasta 'data' exista
CAMINHO_CACHE_DB = CAMINHO_PASTA_DATA / "cache.db"

# Defina aqui se deseja FORÇAR a limpeza do cache e buscar dados novos do banco
FORCAR_ATUALIZACAO_DO_BANCO: bool = False

# Bases que você deseja analisar no estudo de hoje
bases_alvo = ["plancc", "fatofechamento"]

# %% [markdown]
# ### Funções Auxiliares do Cache Local (SQLite)

# %%
def verificar_tabela_existe_no_cache(nome_tabela: str, conexao: sqlite3.Connection) -> bool:
    """Verifica se a tabela solicitada já existe gravada no arquivo SQLite local."""
    query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{nome_tabela}'"
    res = pd.read_sql_query(query, conexao)
    return not res.empty

def obter_dados_com_cache(bases: list[str], forcar_update: bool = False) -> dict[str, pd.DataFrame]:
    """
    Política Read-Through: Busca dados locais do SQLite ou aciona 
    o pipeline de rede apenas para as tabelas ausentes.
    """
    dados_finais: dict[str, pd.DataFrame] = {}
    bases_faltantes: list[str] = []

    # Se não forçar atualização e o arquivo .db existir, tenta ler o cache primeiro
    if not forcar_update and CAMINHO_CACHE_DB.exists():
        with sqlite3.connect(CAMINHO_CACHE_DB) as conn:
            for base in bases:
                if verificar_tabela_existe_no_cache(base, conn):
                    print(f"-> [CACHE LOCAL] Carregando tabela '{base}' do SQLite...")
                    dados_finais[base] = pd.read_sql_query(f"SELECT * FROM [{base}]", conn)
                else:
                    bases_faltantes.append(base)
    else:
        # Se forçar o update, todas as bases são marcadas como faltantes para serem recarregadas
        bases_faltantes = list(bases)

    # Se existirem bases que não estão no cache local, busca do SQL Server e atualiza o .db
    if bases_faltantes:
        print(f"-> [SQL SERVER] Buscando bases ausentes do banco FINANCA: {bases_faltantes}...")
        novos_dados = asyncio.run(obter_dados_carregados_em_memoria(bases_faltantes))
        
        if novos_dados:
            with sqlite3.connect(CAMINHO_CACHE_DB) as conn:
                for base, df in novos_dados.items():
                    if df is not None and not df.empty:
                        # Grava o DataFrame de forma compacta e indexada no SQLite local
                        df.to_sql(base, conn, if_exists="replace", index=False)
                        print(f"-> [CACHE LOCAL] Tabela '{base}' cacheada com sucesso.")
                        dados_finais[base] = df
                        
    return dados_finais

# %% [markdown]
# ### Execução do Carregamento com Cache Ativo

# %%
# Carrega as bases de forma híbrida e ultra veloz
dados_estudo = obter_dados_com_cache(bases_alvo, forcar_update=FORCAR_ATUALIZACAO_DO_BANCO)
print(f"\nTabelas prontas para estudo em memória: {list(dados_estudo.keys())}")

# %% [markdown]
# ### Exploração e Estudos Analíticos

# %%
# Análise do fatofechamento
if "fatofechamento" in dados_estudo:
    df_fatos = dados_estudo["fatofechamento"]
    print(f"\n[FATOFECHAMENTO] Volume de registros: {len(df_fatos)}")
    display(df_fatos.head())

# %%
# Análise do plancc
if "plancc" in dados_estudo:
    df_plancc = dados_estudo["plancc"]
    print(f"\n[PLANCC] Volume de registros: {len(df_plancc)}")
    display(df_plancc.head())

# %% [markdown]
# ### Validação e Agrupamento Estatístico (Ajustado)

# %%
if "fatofechamento" in dados_estudo:
    df_fatos = dados_estudo["fatofechamento"]
    
    # Ajustado: Inserido o agrupamento correto pela coluna 'nm_cc' (conforme seu de/para)
    coluna_grupo = "nm_cc"
    coluna_valor = "vl_valor"
    
    if coluna_grupo in df_fatos.columns and coluna_valor in df_fatos.columns:
        print(f"\nSoma total de valores agrupada por {coluna_grupo}:")
        resumo = df_fatos.groupby(coluna_grupo)[coluna_valor].sum().reset_index()
        display(resumo.sort_values(by=coluna_valor, ascending=False).head(10))

# 1. Ajusta os tipos e filtra o df_fatos (como fizemos antes)
df_fatos['ano_fatos'] = pd.to_datetime(df_fatos['nm_data']).dt.year

# Filtre pelo ano que você deseja (ex: 2026)
df_fatos_filtrado = df_fatos[df_fatos['ano_fatos'].isin([2025, 2026])][[
    'nm_cc', 'ano_fatos', 'nm_conta', 'vl_valor', 'cdg_codtmv', 'cdg_contrato',
    'nm_fornecedor', 'nm_data', 'nm_projeto', 'nm_acao', 'nm_unidade',
    'nm_descnvl6', 'nm_descnvl5', 'nm_descnvl4', 'nm_descnvl3', 'nm_descnvl2', 'nm_descnvl1'
]]

# CORREÇÃO DO ERRO: Converte 'vl_ano' do df_plancc para inteiro antes do merge
df_plancc['vl_ano'] = df_plancc['vl_ano'].astype(int)

# 2. Executa o Merge com os tipos agora idênticos
df_resultado = pd.merge(
    df_plancc[['nm_cc', 'vl_ano', 'cdg_natorcamentonvl4', 'nm_natorcamentonvl4', 'vl_mes', 'vl_ajustado']],
    df_fatos_filtrado,
    left_on=['nm_cc', 'vl_ano'],      
    right_on=['nm_cc', 'ano_fatos'],  
    how='left'
)
display(df_resultado.head())

# %% [markdown]
# ### Geração de Gráficos Diretos com Seaborn
# Exemplo direto de como gerar um gráfico de barras horizontais simples no resultado do seu Merge.

# %%
import seaborn as sns
import matplotlib.pyplot as plt

# 1. Agrupa de forma simples as contas do merge por soma de valor orçado e filtra o Top 10
resumo_grafico = (
    df_resultado.groupby(["nm_natorcamentonvl4"])[["vl_valor","vl_ajustado"]]
    .sum()
    .reset_index()
    .sort_values(by="vl_valor", ascending=False))

# 2. Configura e desenha o gráfico de barras horizontais usando Seaborn
plt.figure(figsize=(10, 5))
sns.barplot(
    data=resumo_grafico, 
    x="vl_valor", 
    y="nm_natorcamentonvl4",  # Ajuste para a coluna correta do nome da conta
    palette="viridis",
    hue="nm_natorcamentonvl4",
    legend=False
)

# 3. Adiciona os títulos e exibe em tela
plt.title("Contas Orçamentárias por Gasto de Realizado", fontsize=12)
plt.xlabel("Valor Total Realizado (R$)")
plt.ylabel("Conta Orçamentária")
plt.tight_layout()

# MANDATÓRIO: Mostra o gráfico na janela interativa do VS Code
plt.show()


plt.figure(figsize=(12, 5))

# Linha 1: Valor Orçado (Ajustado)
sns.lineplot(data=resumo_grafico, x="nm_natorcamentonvl4", y="vl_ajustado", label="Orçado", marker="o")

# Linha 2: Valor Realizado (Gasto)
sns.lineplot(data=resumo_grafico, x="nm_natorcamentonvl4", y="vl_valor", label="Realizado", marker="o")

# Ajuste estético para os nomes das naturezas não ficarem amontoados
plt.xticks(rotation=45, ha="right")
plt.ylabel("Valores (R$)")
plt.xlabel("Natureza Orçamentária")
plt.tight_layout()

plt.show()

# %%
