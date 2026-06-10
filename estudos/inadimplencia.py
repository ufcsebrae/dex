# %% [markdown]
# # Painel de Inteligência Financeira e Auditoria de Inadimplência - DEX
# Divisão de estudo analítico em dois universos: Universo Total de Caixa vs Universo de Inadimplência.

# %%
import sys
import sqlite3
import asyncio  
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 1. Configura caminhos e importa funções da raiz do projeto
DIRETORIO_RAIZ = Path(__file__).resolve().parents[1]
if str(DIRETORIO_RAIZ) not in sys.path:
    sys.path.insert(0, str(DIRETORIO_RAIZ))

from main import obter_dados_carregados_em_memoria

# Busca os dados de inadimplência da carga (FINANCA)
bases_alvo = ["inadim"]
dados_estudo = asyncio.run(obter_dados_carregados_em_memoria(bases_alvo))

# %% [markdown]
# ## 2. Normalização e Regras de Negócio de Base

# %%
if "inadim" in dados_estudo:
    df_inadim = dados_estudo["inadim"].copy()
    
    # Normalização de tipos de dados e datas
    df_inadim['dt_datavencimento'] = pd.to_datetime(df_inadim['dt_datavencimento'])
    df_inadim['dt_databaixa'] = pd.to_datetime(df_inadim['dt_databaixa'])
    df_inadim['dt_datacriacao'] = pd.to_datetime(df_inadim['dt_datacriacao'])
    df_inadim['cdg_idmov'] = df_inadim['cdg_idmov'].astype('Int64').astype(str)
    
    # Conversão de colunas de valores (Cabeçalho vs Parcela)
    coluna_bruto = 'vl_bruto' if 'vl_bruto' in df_inadim.columns else 'vl_valororiginal'
    df_inadim['vl_bruto'] = pd.to_numeric(df_inadim[coluna_bruto], errors='coerce').fillna(0.0)
    df_inadim['vl_valororiginal'] = pd.to_numeric(df_inadim['vl_valororiginal'], errors='coerce').fillna(0.0)
    df_inadim['vl_valorbaixado'] = pd.to_numeric(df_inadim['vl_valorbaixado'], errors='coerce').fillna(0.0)
    
    hoje = pd.Timestamp.now()
    hoje_ano_passado = hoje - pd.DateOffset(years=1)
    
    # 1. Classificação Simplificada de Status Geral ( nm_descstatuslcto )
    df_inadim['status_simplificado'] = df_inadim['nm_descstatuslcto'].apply(
        lambda x: 'Baixado' if str(x).strip().lower() == 'baixado' else 'Em Aberto'
    )
    
    # 2. Definição das Safras Temporais por Vencimento
    df_inadim['ano_venc'] = df_inadim['dt_datavencimento'].dt.year
    df_inadim['mes_venc'] = df_inadim['dt_datavencimento'].dt.month
    
    # Filtra apenas os anos de interesse da análise (2025 e 2026)
    df_analise = df_inadim[df_inadim['ano_venc'].isin([2025, 2026])].copy()
    
    # 3. Regra de Inadimplência (Guardada na tabela fato para a Parte II)
    df_analise['is_inadimplente'] = (
        (df_analise['dt_databaixa'] > df_analise['dt_datavencimento']) | 
        (df_analise['dt_databaixa'].isna() & (df_analise['dt_datavencimento'] < hoje))
    )

# %% [markdown]
# # ==============================================================================
# # PARTE I: O UNIVERSO TOTAL (Faturamento e Liquidação Geral do Caixa)
# # ==============================================================================

# %% [markdown]
# ### I.1: Indicadores por NÚMERO DE PARCELAS (Quantidade Geral - Universo Total)

# %%
if "inadim" in dados_estudo:
    # Total de parcelas a vencer/vencidas por mês de vencimento
    tot_parcelas_geral = df_analise.groupby(['ano_venc', 'mes_venc'])['cdg_idlan'].count().reset_index(name='total_parcelas')
    
    # Contagem de parcelas por status (Pagas vs Em Aberto)
    pivot_qtd_geral = df_analise.pivot_table(
        index=['ano_venc', 'mes_venc'],
        columns='status_simplificado',
        values='cdg_idlan',
        aggfunc='count',
        fill_value=0
    ).reset_index()
    
    df_qtd_geral = pd.merge(pivot_qtd_geral, tot_parcelas_geral, on=['ano_venc', 'mes_venc'], how='left')
    
    # Cálculos percentuais por quantidade de parcelas
    df_qtd_geral['pct_baixado_qtd'] = ((df_qtd_geral['Baixado'] / df_qtd_geral['total_parcelas']) * 100).round(2)
    df_qtd_geral['pct_aberto_qtd'] = ((df_qtd_geral['Em Aberto'] / df_qtd_geral['total_parcelas']) * 100).round(2)
    
    print("=== TABELA I.1: % EMISSÃO DE PARCELAS POR STATUS (UNIVERSO TOTAL) ===")
    display(df_qtd_geral[['ano_venc', 'mes_venc', 'pct_baixado_qtd', 'pct_aberto_qtd']].head(15))

# %% [markdown]
# ### I.2: GRÁFICO I.1: Emissão e Liquidação por QUANTIDADE DE PARCELAS (%)

# %%
if "inadim" in dados_estudo:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5), sharey=True)
    sns.set_theme(style="whitegrid")
    
    # --- GRÁFICO 2025 (Quantidade Geral) ---
    df_qtd_2025 = df_qtd_geral[df_qtd_geral['ano_venc'] == 2025].sort_values('mes_venc')
    ax1.plot(df_qtd_2025['mes_venc'], df_qtd_2025['pct_baixado_qtd'], marker='o', linewidth=2.5, color='#2ca02c', label='% Parcelas Liquidadas (Pagas)')
    ax1.plot(df_qtd_2025['mes_venc'], df_qtd_2025['pct_aberto_qtd'], marker='o', linewidth=2.5, color='#7f7f7f', label='% Parcelas em Aberto (Ativas/A Vencer)')
    
    for x, y_b, y_a in zip(df_qtd_2025['mes_venc'], df_qtd_2025['pct_baixado_qtd'], df_qtd_2025['pct_aberto_qtd']):
        if y_b > 0: ax1.text(x, y_b + 2, f"{y_b:.1f}%", ha='center', va='bottom', fontsize=8, color='#1b5e20', weight='bold')
        if y_a > 0: ax1.text(x, y_a + 2, f"{y_a:.1f}%", ha='center', va='bottom', fontsize=8, color='#424242', weight='bold')
            
    ax1.set_title("Safra por QTD DE PARCELAS - Ano 2025 (Universo Total)", fontsize=11, fontweight='bold', pad=10)
    ax1.set_ylabel("Proporção sobre o Total de Parcelas (%)")
    ax1.set_xlabel("Mês de Vencimento")
    ax1.set_xticks(range(1, 13))
    ax1.set_xticklabels(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    ax1.legend(loc="upper right", fontsize=8.5)
    ax1.set_ylim(-2, 105)

    # --- GRÁFICO 2026 (Quantidade Geral) ---
    df_qtd_2026 = df_qtd_geral[df_qtd_geral['ano_venc'] == 2026].sort_values('mes_venc')
    ax2.plot(df_qtd_2026['mes_venc'], df_qtd_2026['pct_baixado_qtd'], marker='o', linewidth=2.5, color='#2ca02c', label='% Parcelas Liquidadas (Pagas)')
    ax2.plot(df_qtd_2026['mes_venc'], df_qtd_2026['pct_aberto_qtd'], marker='o', linewidth=2.5, color='#7f7f7f', label='% Parcelas em Aberto (Ativas/A Vencer)')
    
    for x, y_b, y_a in zip(df_qtd_2026['mes_venc'], df_qtd_2026['pct_baixado_qtd'], df_qtd_2026['pct_aberto_qtd']):
        if y_b > 0: ax2.text(x, y_b + 2, f"{y_b:.1f}%", ha='center', va='bottom', fontsize=8, color='#1b5e20', weight='bold')
        if y_a > 0: ax2.text(x, y_a + 2, f"{y_a:.1f}%", ha='center', va='bottom', fontsize=8, color='#424242', weight='bold')
            
    ax2.set_title("Safra por QTD DE PARCELAS - Ano 2026 (Universo Total)", fontsize=11, fontweight='bold', pad=10)
    ax2.set_xlabel("Mês de Vencimento")
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    ax2.legend(loc="upper right", fontsize=8.5)
    
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ### I.3: Indicadores por VOLUME FINANCEIRO (Valor em R$ - Universo Total)

# %%
if "inadim" in dados_estudo:
    # REGRA DE OURO: Deduplicação de faturas (IDMOV) no faturamento bruto para evitar sobre-contagem
    df_faturas_unicas = df_analise.drop_duplicates(subset=['ano_venc', 'mes_venc', 'cdg_idmov'])
    faturamento_bruto = df_faturas_unicas.groupby(['ano_venc', 'mes_venc'])['vl_bruto'].sum().reset_index(name='total_faturamento_bruto')
    
    # Soma financeira de TODAS as parcelas baixadas (pagas no prazo ou fora)
    baixado_geral_valor = df_analise.groupby(['ano_venc', 'mes_venc'])['vl_valorbaixado'].sum().reset_index(name='valor_baixado_geral')
    
    # Soma financeira de parcelas abertas gerais (a vencer ou vencidas)
    df_aberto_geral = df_analise[df_analise['status_simplificado'] == 'Em Aberto']
    aberto_geral_valor = df_aberto_geral.groupby(['ano_venc', 'mes_venc'])['vl_valororiginal'].sum().reset_index(name='valor_aberto_geral')

    # Unificação financeira das tabelas
    df_valores_geral = pd.merge(faturamento_bruto, baixado_geral_valor, on=['ano_venc', 'mes_venc'], how='left')
    df_valores_geral = pd.merge(df_valores_geral, aberto_geral_valor, on=['ano_venc', 'mes_venc'], how='left').fillna(0.0)
    
    # Cálculos percentuais financeiros sobre o faturamento real deduplicado
    df_valores_geral['pct_baixado_val'] = ((df_valores_geral['valor_baixado_geral'] / df_valores_geral['total_faturamento_bruto']) * 100).round(2)
    df_valores_geral['pct_aberto_val'] = ((df_valores_geral['valor_aberto_geral'] / df_valores_geral['total_faturamento_bruto']) * 100).round(2)
    
    print("=== TABELA I.2: % INADIMPLÊNCIA FINANCEIRA (R$ - UNIVERSO TOTAL) ===")
    display(df_valores_geral[['ano_venc', 'mes_venc', 'pct_baixado_val', 'pct_aberto_val']].head(15))

# %% [markdown]
# ### I.4: GRÁFICO I.2: Safra de Inadimplência por VOLUME FINANCEIRO (Universo Total %)

# %%
if "inadim" in dados_estudo:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5), sharey=True)
    
    # --- GRÁFICO 2025 (Financeiro Geral) ---
    df_val_2025 = df_valores_geral[df_valores_geral['ano_venc'] == 2025].sort_values('mes_venc')
    ax1.plot(df_val_2025['mes_venc'], df_val_2025['pct_baixado_val'], marker='o', linewidth=2.5, color='#2ca02c', label='% Financeiro Liquidado (Baixado)')
    ax1.plot(df_val_2025['mes_venc'], df_val_2025['pct_aberto_val'], marker='o', linewidth=2.5, color='#7f7f7f', label='% Financeiro em Aberto (Ativo)')
    
    for x, y_b, y_a in zip(df_val_2025['mes_venc'], df_val_2025['pct_baixado_val'], df_val_2025['pct_aberto_val']):
        if y_b > 0: ax1.text(x, y_b + 2, f"{y_b:.1f}%", ha='center', va='bottom', fontsize=8, color='#2ca02c', weight='bold')
        if y_a > 0: ax1.text(x, y_a + 2, f"{y_a:.1f}%", ha='center', va='bottom', fontsize=8, color='#424242', weight='bold')
            
    ax1.set_title("Safra por VOLUME FINANCEIRO - Ano 2025 (Universo Total)", fontsize=11, fontweight='bold', pad=10)
    ax1.set_ylabel("Proporção sobre o Faturamento Bruto Real (%)")
    ax1.set_xlabel("Mês de Vencimento")
    ax1.set_xticks(range(1, 13))
    ax1.set_xticklabels(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    ax1.legend(loc="upper right", fontsize=8.5)
    ax1.set_ylim(-2, 105)

    # --- GRÁFICO 2026 (Financeiro Geral) ---
    df_val_2026 = df_valores_geral[df_valores_geral['ano_venc'] == 2026].sort_values('mes_venc')
    ax2.plot(df_val_2026['mes_venc'], df_val_2026['pct_baixado_val'], marker='o', linewidth=2.5, color='#2ca02c', label='% Financeiro Liquidado (Baixado)')
    ax2.plot(df_val_2026['mes_venc'], df_val_2026['pct_aberto_val'], marker='o', linewidth=2.5, color='#7f7f7f', label='% Financeiro em Aberto (Ativo)')
    
    for x, y_b, y_a in zip(df_val_2026['mes_venc'], df_val_2026['pct_baixado_val'], df_val_2026['pct_aberto_val']):
        if y_b > 0: ax2.text(x, y_b + 2, f"{y_b:.1f}%", ha='center', va='bottom', fontsize=8, color='#2ca02c', weight='bold')
        if y_a > 0: ax2.text(x, y_a + 2, f"{y_a:.1f}%", ha='center', va='bottom', fontsize=8, color='#424242', weight='bold')
            
    ax2.set_title("Safra por VOLUME FINANCEIRO - Ano 2026 (Universo Total)", fontsize=11, fontweight='bold', pad=10)
    ax2.set_xlabel("Mês de Vencimento")
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    ax2.legend(loc="upper right", fontsize=8.5)
    
    plt.tight_layout()
    plt.show()

# %% [markdown]
# # ==============================================================================
# # PARTE II: O UNIVERSO INADIMPLENTE (Risco de Crédito, Atrasados e Perdas)
# # ==============================================================================

# %% [markdown]
# ### II.1: Indicadores por NÚMERO DE PARCELAS (Inadimplência Ativa e Atrasos)

# %%
if "inadim" in dados_estudo:
    # Filtra estritamente para o sub-universo de inadimplentes ativos
    df_inad_ativos = df_analise[df_analise['is_inadimplente']].copy()
    
    # Total de parcelas inadimplentes no período
    tot_parcelas_inad = df_inad_ativos.groupby(['ano_venc', 'mes_venc'])['cdg_idlan'].count().reset_index(name='total_parcelas_inad')
    
    # Contagem por status do devedor (Baixado/Atrasado vs Em Aberto/Perda)
    pivot_qtd_inad = df_inad_ativos.pivot_table(
        index=['ano_venc', 'mes_venc'],
        columns='status_simplificado',
        values='cdg_idlan',
        aggfunc='count',
        fill_value=0
    ).reset_index()
    
    # Blindagem
    if 'Baixado' not in pivot_qtd_inad.columns: pivot_qtd_inad['Baixado'] = 0
    if 'Em Aberto' not in pivot_qtd_inad.columns: pivot_qtd_inad['Em Aberto'] = 0
    
    df_qtd_inad = pd.merge(pivot_qtd_inad, tot_parcelas_inad, on=['ano_venc', 'mes_venc'], how='left')
    
    # Cálculos percentuais sob o universo de devedores
    df_qtd_inad['pct_baixado_qtd'] = ((df_qtd_inad['Baixado'] / df_qtd_inad['total_parcelas_inad']) * 100).round(2)
    df_qtd_inad['pct_aberto_qtd'] = ((df_qtd_inad['Em Aberto'] / df_qtd_inad['total_parcelas_inad']) * 100).round(2)
    
    print("=== TABELA II.1: % RECUPERAÇÃO vs PERDAS (QTD PARCELAS INADIMPLENTES) ===")
    display(df_qtd_inad[['ano_venc', 'mes_venc', 'pct_baixado_qtd', 'pct_aberto_qtd']].head(15))

# %% [markdown]
# ### II.2: GRÁFICO II.1: Safra de Inadimplência por QUANTIDADE DE PARCELAS (Devedores %)

# %%
if "inadim" in dados_estudo:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5), sharey=True)
    
    # --- GRÁFICO 2025 (Inadimplência Qtd) ---
    df_qtd_inad_25 = df_qtd_inad[df_qtd_inad['ano_venc'] == 2025].sort_values('mes_venc')
    ax1.plot(df_qtd_inad_25['mes_venc'], df_qtd_inad_25['pct_baixado_qtd'], marker='o', linewidth=2.5, color='#D97706', label='% Pago em Atraso (Recuperado)')
    ax1.plot(df_qtd_inad_25['mes_venc'], df_qtd_inad_25['pct_aberto_qtd'], marker='o', linewidth=2.5, color='#991B1B', label='% Ativo Pendente (Perda Real)')
    
    for x, y_b, y_a in zip(df_qtd_inad_25['mes_venc'], df_qtd_inad_25['pct_baixado_qtd'], df_qtd_inad_25['pct_aberto_qtd']):
        if y_b > 0: ax1.text(x, y_b + 2, f"{y_b:.1f}%", ha='center', va='bottom', fontsize=8, color='#D97706', weight='bold')
        if y_a > 0: ax1.text(x, y_a + 2, f"{y_a:.1f}%", ha='center', va='bottom', fontsize=8, color='#991B1B', weight='bold')
            
    ax1.set_title("Safra por QTD DE PARCELAS - Ano 2025 (Inadimplentes)", fontsize=11, fontweight='bold', pad=10)
    ax1.set_ylabel("Proporção sob o Universo de Devedores (%)")
    ax1.set_xlabel("Mês de Vencimento")
    ax1.set_xticks(range(1, 13))
    ax1.set_xticklabels(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    ax1.legend(loc="upper right", fontsize=8.5)
    ax1.set_ylim(-2, 105)

    # --- GRÁFICO 2026 (Inadimplência Qtd) ---
    df_qtd_inad_26 = df_qtd_inad[df_qtd_inad['ano_venc'] == 2026].sort_values('mes_venc')
    ax2.plot(df_qtd_inad_26['mes_venc'], df_qtd_inad_26['pct_baixado_qtd'], marker='o', linewidth=2.5, color='#D97706', label='% Pago em Atraso (Recuperado)')
    ax2.plot(df_qtd_inad_26['mes_venc'], df_qtd_inad_26['pct_aberto_qtd'], marker='o', linewidth=2.5, color='#991B1B', label='% Ativo Pendente (Perda Real)')
    
    for x, y_b, y_a in zip(df_qtd_inad_26['mes_venc'], df_qtd_inad_26['pct_baixado_qtd'], df_qtd_inad_26['pct_aberto_qtd']):
        if y_b > 0: ax2.text(x, y_b + 2, f"{y_b:.1f}%", ha='center', va='bottom', fontsize=8, color='#D97706', weight='bold')
        if y_a > 0: ax2.text(x, y_a + 2, f"{y_a:.1f}%", ha='center', va='bottom', fontsize=8, color='#991B1B', weight='bold')
            
    ax2.set_title("Safra por QTD DE PARCELAS - Ano 2026 (Inadimplentes)", fontsize=11, fontweight='bold', pad=10)
    ax2.set_xlabel("Mês de Vencimento")
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    ax2.legend(loc="upper right", fontsize=8.5)
    
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ### II.3: Indicadores por VOLUME FINANCEIRO (Valor em R$ - Inadimplentes)

# %%
if "inadim" in dados_estudo:
    # Faturamento Bruto de Inadimplência (Deduplicado por IDMOV dos inadimplentes)
    df_faturas_inad_unicas = df_inad_ativos.drop_duplicates(subset=['ano_venc', 'mes_venc', 'cdg_idmov'])
    faturamento_inad_bruto = df_faturas_inad_unicas.groupby(['ano_venc', 'mes_venc'])['vl_bruto'].sum().reset_index(name='total_bruto_inad')
    
    # Soma financeira de parcelas inadimplentes de fato pagas em atraso (Baixado)
    df_baixados_atraso_inad = df_inad_ativos[df_inad_ativos['status_simplificado'] == 'Baixado']
    baixados_atraso_valor_inad = df_baixados_atraso_inad.groupby(['ano_venc', 'mes_venc'])['vl_valorbaixado'].sum().reset_index(name='valor_baixado_atraso_inad')
    
    # Soma financeira de parcelas inadimplentes abertas (Em Aberto)
    df_aberto_inad_inad = df_inad_ativos[df_inad_ativos['status_simplificado'] == 'Em Aberto']
    aberto_inad_valor_inad = df_aberto_inad_inad.groupby(['ano_venc', 'mes_venc'])['vl_valororiginal'].sum().reset_index(name='valor_aberto_inad_inad')

    # Unificação financeira das tabelas de devedores
    df_valores_inad = pd.merge(faturamento_inad_bruto, baixados_atraso_valor_inad, on=['ano_venc', 'mes_venc'], how='left')
    df_valores_inad = pd.merge(df_valores_inad, aberto_inad_valor_inad, on=['ano_venc', 'mes_venc'], how='left').fillna(0.0)
    
    # Cálculos percentuais financeiros sobre o faturamento de inadimplência deduplicado
    df_valores_inad['pct_baixado_val'] = ((df_valores_inad['valor_baixado_atraso_inad'] / df_valores_inad['total_bruto_inad']) * 100).round(2)
    df_valores_inad['pct_aberto_val'] = ((df_valores_inad['valor_aberto_inad_inad'] / df_valores_inad['total_bruto_inad']) * 100).round(2)
    
    print("=== TABELA II.2: % RECUPERAÇÃO vs PERDA FINANCEIRA (R$ DEVEDORES) ===")
    display(df_valores_inad[['ano_venc', 'mes_venc', 'pct_baixado_val', 'pct_aberto_val']].head(15))

# %% [markdown]
# ### II.4: GRÁFICO II.2: Safra de Inadimplência por VOLUME FINANCEIRO (Devedores %)

# %%
if "inadim" in dados_estudo:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5), sharey=True)
    
    # --- GRÁFICO 2025 (Inadimplência Valor) ---
    df_val_inad_25 = df_valores_inad[df_valores_inad['ano_venc'] == 2025].sort_values('mes_venc')
    ax1.plot(df_val_inad_25['mes_venc'], df_val_inad_25['pct_baixado_val'], marker='o', linewidth=2.5, color='#D97706', label='% Gasto Pago em Atraso (Baixado)')
    ax1.plot(df_val_inad_25['mes_venc'], df_val_inad_25['pct_aberto_val'], marker='o', linewidth=2.5, color='#991B1B', label='% Gasto Ativo Pendente (Em Aberto)')
    
    for x, y_b, y_a in zip(df_val_inad_25['mes_venc'], df_val_inad_25['pct_baixado_val'], df_val_inad_25['pct_aberto_val']):
        if y_b > 0: ax1.text(x, y_b + 2, f"{y_b:.1f}%", ha='center', va='bottom', fontsize=8, color='#D97706', weight='bold')
        if y_a > 0: ax1.text(x, y_a + 2, f"{y_a:.1f}%", ha='center', va='bottom', fontsize=8, color='#991B1B', weight='bold')
            
    ax1.set_title("Safra por VOLUME FINANCEIRO - Ano 2025 (Inadimplentes)", fontsize=11, fontweight='bold', pad=10)
    ax1.set_ylabel("Proporção sobre o Faturamento Bruto de Inadimplência (%)")
    ax1.set_xlabel("Mês de Vencimento")
    ax1.set_xticks(range(1, 13))
    ax1.set_xticklabels(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    ax1.legend(loc="upper right", fontsize=8.5)
    ax1.set_ylim(-2, 105)

    # --- GRÁFICO 2026 (Inadimplência Valor) ---
    df_val_inad_26 = df_valores_inad[df_valores_inad['ano_venc'] == 2026].sort_values('mes_venc')
    ax2.plot(df_val_inad_26['mes_venc'], df_val_inad_26['pct_baixado_val'], marker='o', linewidth=2.5, color='#D97706', label='% Gasto Pago em Atraso (Baixado)')
    ax2.plot(df_val_inad_26['mes_venc'], df_val_inad_26['pct_aberto_val'], marker='o', linewidth=2.5, color='#991B1B', label='% Gasto Ativo Pendente (Em Aberto)')
    
    for x, y_b, y_a in zip(df_val_inad_26['mes_venc'], df_val_inad_26['pct_baixado_val'], df_val_inad_26['pct_aberto_val']):
        if y_b > 0: ax2.text(x, y_b + 2, f"{y_b:.1f}%", ha='center', va='bottom', fontsize=8, color='#D97706', weight='bold')
        if y_a > 0: ax2.text(x, y_a + 2, f"{y_a:.1f}%", ha='center', va='bottom', fontsize=8, color='#991B1B', weight='bold')
            
    ax2.set_title("Safra por VOLUME FINANCEIRO - Ano 2026 (Inadimplentes)", fontsize=11, fontweight='bold', pad=10)
    ax2.set_xlabel("Mês de Vencimento")
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    ax2.legend(loc="upper right", fontsize=8.5)
    
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ## II.5: Tabelas Consolidadas Individuais para Auditoria de Risco (Roteamento Amigável)

# %%
if "inadim" in dados_estudo:
    colunas_auditoria_bruta = [
        'dt_datavencimento', 'dt_databaixa', 'vl_bruto', 'vl_valororiginal', 
        'cdg_codtmv', 'nm_descstatuslcto', 'status_simplificado', 'nm_historico'
    ]
    
    de_para_colunas_amigaveis = {
        'dt_datavencimento': 'Data Vencimento',
        'dt_databaixa': 'Data Baixa',
        'vl_bruto': 'Valor Total da Fatura (IDMOV)',          # Faturamento
        'vl_valororiginal': 'Valor desta Parcela (Individual)', # Item da Parcela
        'cdg_codtmv': 'Tipo Movimento',
        'nm_descstatuslcto': 'Status Lançamento',
        'status_simplificado': 'Status Simplificado',
        'nm_historico': 'Histórico'
    }

    # 1. TABELA 1: Inadimplentes referentes ao Ano de 2025
    df_inad_2025_raw = df_inad_ativos[df_inad_ativos['ano_venc'] == 2025].sort_values(by='vl_bruto', ascending=False)[colunas_auditoria_bruta]
    df_inad_2025_raw = df_inad_2025_raw.rename(columns=de_para_colunas_amigaveis)
    
    print("=== TABELA II.3: TODOS OS INADIMPLENTES DO ANO DE 2025 ===")
    print(f"Volume total: {len(df_inad_2025_raw)} parcelas em atraso.")
    display(df_inad_2025_raw.head(100))

    # 2. TABELA 2: Inadimplentes referentes ao Ano de 2026
    df_inad_2026_raw = df_inad_ativos[df_inad_ativos['ano_venc'] == 2026].sort_values(by='vl_bruto', ascending=False)[colunas_auditoria_bruta]
    df_inad_2026_raw = df_inad_2026_raw.rename(columns=de_para_colunas_amigaveis)
    
    print("\n=== TABELA II.4: TODOS OS INADIMPLENTES DO ANO DE 2026 ===")
    print(f"Volume total: {len(df_inad_2026_raw)} parcelas em atraso.")
    display(df_inad_2026_raw.head(100))

    # 3. TABELA 3: Inadimplentes de 2026 que já foram Baixados (Pagos com atraso)
    df_inad_baixados_2026 = df_inad_ativos[
        (df_inad_ativos['ano_venc'] == 2026) & 
        (df_inad_ativos['status_simplificado'] == 'Baixado')
    ].sort_values(by='vl_bruto', ascending=False)[colunas_auditoria_bruta]
    
    df_inad_baixados_2026 = df_inad_baixados_2026.rename(columns=de_para_colunas_amigaveis)
    
    print("\n=== TABELA II.5: INADIMPLENTES DE 2026 QUE JÁ FORAM BAIXADOS (PAGOS COM ATRASO) ===")
    print(f"Volume total: {len(df_inad_baixados_2026)} parcelas em atraso liquidadas.")
    display(df_inad_baixados_2026.head(100))
