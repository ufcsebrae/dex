# %%
import sys
import sqlite3
import asyncio  
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

DIRETORIO_RAIZ = Path(__file__).resolve().parents[1]
if str(DIRETORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRETORIO_RAIZ))

from main import obter_dados_carregados_em_memoria

# 1. Busca os dados de inadimplência do banco
bases_alvo = ["inadim"]
dados_estudo = asyncio.run(obter_dados_carregados_em_memoria(bases_alvo))

# %% [markdown]
# ## 2. Processamento e Criação da Tabela
# Nesta célula realizamos os filtros temporais (até a data atualizada do ano passado) 
# e montamos a tabela comparativa mês a mês.

# %%
if "inadim" in dados_estudo:
    df_inadim = dados_estudo["inadim"].copy()
    
    # Ajusta os tipos de dados
    df_inadim['dt_datavencimento'] = pd.to_datetime(df_inadim['dt_datavencimento'])
    df_inadim['dt_databaixa'] = pd.to_datetime(df_inadim['dt_databaixa'])
    df_inadim['dt_datacriacao'] = pd.to_datetime(df_inadim['dt_datacriacao'])
    df_inadim['vl_valororiginal'] = pd.to_numeric(df_inadim['vl_valororiginal'], errors='coerce')
    df_inadim['cdg_idmov'] = df_inadim['cdg_idmov'].astype('Int64').astype(str)

    #define variavel de data atual e data do ano passado para comparação
    hoje = pd.Timestamp.now()
    hoje_ano_passado = hoje - pd.DateOffset(years=1)
    
    # Aplica a regra de inadimplência
    df_inadim['is_inadimplente'] = (
        (df_inadim['dt_databaixa'] > df_inadim['dt_datavencimento']) | 
        (df_inadim['dt_databaixa'].isna() & (df_inadim['dt_datavencimento'] < hoje))
    )
    
    # Cria as máscaras lógicas comparativas
    mascara_2025 = (df_inadim['dt_datacriacao'].between('2025-01-01', hoje_ano_passado) & df_inadim['is_inadimplente'])
    mascara_2026 = (df_inadim['dt_datacriacao'].between('2026-01-01', hoje) & df_inadim['is_inadimplente'])

    # Define filtros de tabela por ano
    mascara_2025_tot = (df_inadim['dt_datacriacao'].between('2025-01-01', hoje_ano_passado))
    mascara_2026_tot = (df_inadim['dt_datacriacao'].between('2026-01-01', hoje))
    
    # Aplica a máscara inadimplencia
    df_filtrado_2025 = df_inadim[mascara_2025]
    df_filtrado_2026 = df_inadim[mascara_2026]

    # Aplica a mascara de ano
    df_filtrado_2025_tot = df_inadim[mascara_2025_tot]
    df_filtrado_2026_tot = df_inadim[mascara_2026_tot]



    # Contagem total de idmovs únicos no período acumulado
    df_count_idmov_2025 = df_filtrado_2025_tot['cdg_idmov'].nunique()
    df_count_idmov_2026 = df_filtrado_2026_tot['cdg_idmov'].nunique()

    # Agrupamentos mensais
    df_2025_group = df_filtrado_2025_tot.groupby(df_filtrado_2025_tot['dt_datacriacao'].dt.month)['cdg_idmov'].nunique().reset_index(name='2025')
    df_2026_group = df_filtrado_2026_tot.groupby(df_filtrado_2026_tot['dt_datacriacao'].dt.month)['cdg_idmov'].nunique().reset_index(name='2026')
    
    # Junção das tabelas
    df_25x26 = pd.merge(df_2025_group, df_2026_group, on='dt_datacriacao', how='outer')
    df_25x26 = df_25x26.rename(columns={'dt_datacriacao': 'mes'})
    df_25x26 = df_25x26.sort_values('mes').fillna(0)

# %% [markdown]
# ## 3. Resultados e Exibição dos Dados
# Abaixo vemos os totais acumulados de IDMOVs únicos e a tabela comparativa final.

# %%
if "inadim" in dados_estudo:
    print(f"Total IDMOVs Únicos (Até {hoje_ano_passado.strftime('%d/%m/%Y')} em 2025):")
    display(df_count_idmov_2025)
    
    print(f"Total IDMOVs Únicos (Até {hoje.strftime('%d/%m/%Y')} em 2026):")
    display(df_count_idmov_2026)
    
    print("\nTabela Comparativa Mensal:")
    display(df_25x26)

# %% [markdown]
# ## 4. Gráfico Comparativo de Linhas
# Visualização do comportamento mensal das duas safras analisadas.

# %%
if "inadim" in dados_estudo:
    df_grafico = df_25x26.set_index('mes')
    df_grafico.plot(kind='line', marker='o', figsize=(10, 5))

    plt.title('Comparativo de IDMOV: 2025 vs 2026', fontsize=14, fontweight='bold')
    plt.xlabel('Mês', fontsize=12)
    plt.ylabel('Qtd. ID Movimentações Únicas', fontsize=12)
    plt.xticks(range(1, 13)) 
    plt.grid(True, linestyle='--', alpha=0.6) 
    plt.legend(title='Ano')
    plt.show()
