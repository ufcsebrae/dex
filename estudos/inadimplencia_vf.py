# %% [markdown]
# # Painel de Estudos Orçamentários e Auditoria de Risco - DEX
# Análise de safras, faturamento real por IDMOV, contagem de faturas, risco e diagnóstico de outliers por CODTMV.

# %%
import sys
import sqlite3
import asyncio  
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
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
# ## 2. Normalização e Regras de Negócio de Base (Com Corte Temporal Histórico)

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
    
    # Definição dos pontos de corte temporal (Backtesting)
    hoje = pd.Timestamp.now()
    hoje_ano_passado = hoje - pd.DateOffset(years=1)
    
    # Definição das Safras Temporais por Vencimento
    df_inadim['ano_venc'] = df_inadim['dt_datavencimento'].dt.year
    df_inadim['mes_venc'] = df_inadim['dt_datavencimento'].dt.month
    
    # Filtra apenas os anos de interesse da análise (2025 e 2026)
    df_analise = df_inadim[df_inadim['ano_venc'].isin([2025, 2026])].copy()
    
    # INTELIGÊNCIA DE CORTE: Define a data limite de análise baseada no ano do vencimento
    df_analise['data_limite_corte'] = df_analise['ano_venc'].apply(
        lambda ano: hoje_ano_passado if ano == 2025 else hoje
    )
    
    # Regra de Inadimplência
    df_analise['is_inadimplente'] = (
        (df_analise['dt_databaixa'] > df_analise['dt_datavencimento']) | 
        (df_analise['dt_databaixa'].isna() & (df_analise['dt_datavencimento'] < df_analise['data_limite_corte']))
    )
    
    # Regra de Status de Baixa Histórica:
    df_analise['status_simplificado'] = df_analise.apply(
        lambda row: 'Baixado' if (
            str(row['nm_descstatuslcto']).strip().lower() == 'baixado' and 
            row['dt_databaixa'] <= row['data_limite_corte']
        ) else 'Em Aberto',
        axis=1
    )
    
    # Filtros de safras acumuladas de criação para os agrupamentos de CODTMV
    df_filtrado_2025_tot = df_analise[(df_analise['ano_venc'] == 2025) & (df_analise['dt_datacriacao'] <= hoje_ano_passado)].copy()
    df_filtrado_2026_tot = df_analise[(df_analise['ano_venc'] == 2026) & (df_analise['dt_datacriacao'] <= hoje)].copy()
    
    df_filtrado_2025_tot['mes_criacao'] = df_filtrado_2025_tot['dt_datacriacao'].dt.month
    df_filtrado_2026_tot['mes_criacao'] = df_filtrado_2026_tot['dt_datacriacao'].dt.month

# %% [markdown]
# ## 3. Consulta 1: Número de IDMOVs (Faturas Únicas) por Mês e CODTMV (2025 vs 2026)

# %%
if "inadim" in dados_estudo:
    # Agrupa e calcula as faturas únicas por ano e canal
    df_tot_codtmv_25 = df_filtrado_2025_tot.groupby(['mes_criacao', 'cdg_codtmv'])['cdg_idmov'].nunique().reset_index(name='2025')
    df_tot_codtmv_26 = df_filtrado_2026_tot.groupby(['mes_criacao', 'cdg_codtmv'])['cdg_idmov'].nunique().reset_index(name='2026')
    
    # Cruza os anos em formato lado a lado
    df_1_idmovs = pd.merge(df_tot_codtmv_25, df_tot_codtmv_26, on=['cdg_codtmv', 'mes_criacao'], how='outer')
    df_1_idmovs = df_1_idmovs.rename(columns={'cdg_codtmv': 'tipo_mov', 'mes_criacao': 'mes'}).fillna(0)
    df_1_idmovs = df_1_idmovs.sort_values(by=['mes', 'tipo_mov'])
    
    print("=== TABELA 1: QUANTIDADE DE FATURAS ÚNICAS (IDMOVs) POR CODTMV E MÊS ===")
    display(df_1_idmovs.head(15))

    # --- GRÁFICO 1: Múltiplos Pequenos de Volumetria Total ---
    pivot_25 = df_1_idmovs.pivot(index='mes', columns='tipo_mov', values='2025').fillna(0)
    pivot_26 = df_1_idmovs.pivot(index='mes', columns='tipo_mov', values='2026').fillna(0)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True, sharey=True)
    sns.set_theme(style="whitegrid")
    
    pivot_25.plot(kind='line', marker='o', linewidth=2.0, ax=ax1)
    ax1.set_title("Quantidade de Faturas Únicas por Canal em 2025 (Completo)", fontsize=11, fontweight='bold')
    ax1.set_ylabel("Qtd Faturas (IDMOV)")
    ax1.legend(title="Canal (CODTMV)", bbox_to_anchor=(1.02, 1), loc='upper left')
    ax1.grid(True, linestyle='--', alpha=0.5)
    
    pivot_26.plot(kind='line', marker='o', linewidth=2.0, ax=ax2)
    ax2.set_title("Quantidade de Faturas Únicas por Canal em 2026 (Completo)", fontsize=11, fontweight='bold')
    ax2.set_ylabel("Qtd Faturas (IDMOV)")
    ax2.set_xlabel("Mês")
    ax2.legend(title="Canal (CODTMV)", bbox_to_anchor=(1.02, 1), loc='upper left')
    ax2.grid(True, linestyle='--', alpha=0.5)
    
    plt.xticks(range(1, 13), ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ## 4. Consulta 2: Número de IDMOVs por Mês e CODTMV (Sem o movimento 2.1.13)

# %%
if "inadim" in dados_estudo:
    df_2_idmovs_sem_outlier = df_1_idmovs[~df_1_idmovs['tipo_mov'].isin(['2.1.13', '2.1.13.0'])].copy()
    
    print("=== TABELA 2: NÚMERO DE IDMOVS ÚNICOS POR MÊS (SEM 2.1.13) ===")
    display(df_2_idmovs_sem_outlier.head(15))

    # --- GRÁFICO 2: Múltiplos Pequenos de Volumetria (Sem Outlier) ---
    pivot_25_sem = df_2_idmovs_sem_outlier.pivot(index='mes', columns='tipo_mov', values='2025').fillna(0)
    pivot_26_sem = df_2_idmovs_sem_outlier.pivot(index='mes', columns='tipo_mov', values='2026').fillna(0)
    
    fig2, (ax3, ax4) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True, sharey=True)
    
    pivot_25_sem.plot(kind='line', marker='o', linewidth=2.0, ax=ax3)
    ax3.set_title("Quantidade de Faturas Únicas por Canal em 2025 (Sem o movimento 2.1.13)", fontsize=11, fontweight='bold')
    ax3.set_ylabel("Qtd Faturas (IDMOV)")
    ax3.legend(title="Canal (CODTMV)", bbox_to_anchor=(1.02, 1), loc='upper left')
    ax3.grid(True, linestyle='--', alpha=0.5)
    
    pivot_26_sem.plot(kind='line', marker='o', linewidth=2.0, ax=ax4)
    ax4.set_title("Quantidade de Faturas Únicas por Canal em 2026 (Sem o movimento 2.1.13)", fontsize=11, fontweight='bold')
    ax4.set_ylabel("Qtd Faturas (IDMOV)")
    ax4.set_xlabel("Mês")
    ax4.legend(title="Canal (CODTMV)", bbox_to_anchor=(1.02, 1), loc='upper left')
    ax4.grid(True, linestyle='--', alpha=0.5)
    
    plt.xticks(range(1, 13), ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ## 5. Consulta 3: Valor de Inadimplência Ativa na Data por CODTMV e Mês (2025 vs 2026)

# %%
if "inadim" in dados_estudo:
    # Agrupa e soma as perdas financeiras ativas por canal de venda (status_simplificado == 'Em Aberto')
    df_em_aberto = df_analise[df_analise['status_simplificado'] == 'Em Aberto']
    df_4_inad_canal_25 = df_em_aberto[df_em_aberto['ano_venc'] == 2025].groupby(['mes_venc', 'cdg_codtmv'])['vl_valororiginal'].sum().reset_index(name='2025')
    df_4_inad_canal_26 = df_em_aberto[df_em_aberto['ano_venc'] == 2026].groupby(['mes_venc', 'cdg_codtmv'])['vl_valororiginal'].sum().reset_index(name='2026')
    
    # Cruza lado a lado por Canal e Mês
    df_4_inad_canal = pd.merge(df_4_inad_canal_25, df_4_inad_canal_26, on=['cdg_codtmv', 'mes_venc'], how='outer').fillna(0.0)
    df_4_inad_canal = df_4_inad_canal.rename(columns={'cdg_codtmv': 'tipo_mov', 'mes_venc': 'mes'})
    df_4_inad_canal = df_4_inad_canal.sort_values(by=['mes', 'tipo_mov'])
    
    print("=== TABELA 3: VALOR DE INADIMPLÊNCIA ATIVA POR CANAL (CODTMV) E MÊS ===")
    display(df_4_inad_canal.head(15))

    # --- GRÁFICO 3 (Subplots): Curvas de Linha Comparativas de Valores com Eixos Alinhados ---
    pivot_inad_25 = df_4_inad_canal.pivot(index='mes', columns='tipo_mov', values='2025').fillna(0)
    pivot_inad_26 = df_4_inad_canal.pivot(index='mes', columns='tipo_mov', values='2026').fillna(0)
    
    # ALINHAMENTO CORRETIVO: Janela criada definindo explicitamente ax5 e ax6 (PEP 20)
    fig3, (ax5, ax6) = plt.subplots(2, 1, figsize=(12, 8.5), sharex=True, sharey=True)
    
    # Função formatadora para converter notação científica do eixo Y em Milhões (M) ou Milhares (K)
    f_financeiro = ticker.FuncFormatter(
        lambda x, pos: f'R$ {x/1e6:.1f}M' if x >= 1e6 else f'R$ {x/1e3:.0f}K' if x >= 1e3 else f'R$ {x:.0f}'
    )
    
    # Plot 2025 (Ano Passado) - Agora direcionado corretamente ao ax5
    pivot_inad_25.plot(kind='line', marker='o', linewidth=2.0, ax=ax5)
    ax5.set_title("Evolução Financeira do Risco por Canal em 2025 (Inadimplência Ativa)", fontsize=11, fontweight='bold', pad=8)
    ax5.set_ylabel("Valor em Aberto (R$)")
    ax5.yaxis.set_major_formatter(f_financeiro)
    ax5.legend(title="Canal (CODTMV)", bbox_to_anchor=(1.01, 1), loc='upper left')
    ax5.grid(True, linestyle='--', alpha=0.5)
    
    # Plot 2026 (Este Ano) - Agora direcionado corretamente ao ax6
    pivot_inad_26.plot(kind='line', marker='o', linewidth=2.0, ax=ax6)
    ax6.set_title("Evolução Financeira do Risco por Canal em 2026 (Inadimplência Ativa)", fontsize=11, fontweight='bold', pad=8)
    ax6.set_ylabel("Valor em Aberto (R$)")
    ax6.set_xlabel("Mês de Vencimento")
    ax6.yaxis.set_major_formatter(f_financeiro)
    ax6.legend(title="Canal (CODTMV)", bbox_to_anchor=(1.01, 1), loc='upper left')
    ax6.grid(True, linestyle='--', alpha=0.5)
    
    # Ajusta os meses de 1 a 12 de forma clara e visível no eixo X
    plt.xticks(range(1, 13), ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])
    plt.tight_layout()
    plt.show()


# %% [markdown]
# ## 6. Consulta 4: Diagnóstico de Impacto por Canal (CODTMV) e Detalhamento de Outliers (Maiores Inadimplências)

# %%
if "inadim" in dados_estudo:
    # -------------------------------------------------------------------------
    # TABELA 6.1: Impacto Consolidado da Inadimplência por Canal (CODTMV)
    # Mostra qual canal concentrou as maiores perdas somadas e o maior boleto
    # -------------------------------------------------------------------------
    df_impacto_canal = df_em_aberto.groupby(['ano_venc', 'cdg_codtmv']).agg(
        valor_total_em_aberto=('vl_valororiginal', 'sum'),
        maior_boleto_individual=('vl_valororiginal', 'max'),
        quantidade_de_parcelas=('cdg_idlan', 'count')
    ).reset_index()
    
    # Ordena o impacto do maior para o menor para auditar os canais mais críticos
    df_impacto_canal = df_impacto_canal.sort_values(by=['ano_venc', 'valor_total_em_aberto'], ascending=[True, False])
    
    # Renomeação didática
    de_para_impacto = {
        'ano_venc': 'Ano Vencimento',
        'cdg_codtmv': 'Canal (CODTMV)',
        'valor_total_em_aberto': 'Valor Total Acumulado em Aberto (R$)',
        'maior_boleto_individual': 'Maior Boleto Único do Canal (R$)',
        'quantidade_de_parcelas': 'Qtd Parcelas Vencidas'
    }
    df_impacto_canal_friendly = df_impacto_canal.rename(columns=de_para_impacto)
    
    print("=== TABELA 4.1: IMPACTO FINANCEIRO DA INADIMPLÊNCIA POR CANAL DE VENDA (CODTMV) ===")
    display(df_impacto_canal_friendly)

    # -------------------------------------------------------------------------
    # TABELA 6.2: Detalhamento Físico das Maiores Faturas Inadimplentes (Outliers)
    # Exibe as 10 maiores faturas (IDMOVs) em aberto por ano de vencimento
    # -------------------------------------------------------------------------
    colunas_auditoria = [
        'cdg_idmov', 'cdg_codtmv', 'dt_datavencimento', 'vl_bruto', 
        'vl_valororiginal', 'nm_descstatuslcto', 'nm_historico'
    ]
    
    de_para_outliers = {
        'cdg_idmov': 'ID da Fatura (IDMOV)',
        'cdg_codtmv': 'Canal (CODTMV)',
        'dt_datavencimento': 'Data Vencimento',
        'vl_bruto': 'Valor Total da Fatura (IDMOV)',
        'vl_valororiginal': 'Valor desta Parcela (Individual)',
        'nm_descstatuslcto': 'Status Original',
        'nm_historico': 'Histórico Lançamento'
    }
    
    # 2025 - Top 10 Outliers
    inad_2025_raw = df_em_aberto[df_em_aberto['ano_venc'] == 2025]
    top_10_outliers_2025 = inad_2025_raw.sort_values(by='vl_bruto', ascending=False).head(10)[colunas_auditoria]
    top_10_outliers_2025 = top_10_outliers_2025.rename(columns=de_para_outliers)
    
    print("\n=== TABELA 4.2: DETALHAMENTO DAS 10 MAIORES FATURAS EM ABERTO (OUTLIERS) DE 2025 ===")
    display(top_10_outliers_2025)

    # 2026 - Top 10 Outliers
    inad_2026_raw = df_em_aberto[df_em_aberto['ano_venc'] == 2026]
    top_10_outliers_2026 = inad_2026_raw.sort_values(by='vl_bruto', ascending=False).head(10)[colunas_auditoria]
    top_10_outliers_2026 = top_10_outliers_2026.rename(columns=de_para_outliers)
    
    print("\n=== TABELA 4.3: DETALHAMENTO DAS 10 MAIORES FATURAS EM ABERTO (OUTLIERS) DE 2026 ===")
    display(top_10_outliers_2026)
# %% [markdown]
# ## 7. Consolidação da Linha do Tempo Financeira Contínua (2025 + 2026)
# Consolida os 18 meses de série histórica contínua de fluxo de caixa mapeando as três 
# categorias reais de comportamento de pagamento e plota a evolução em um gráfico de linhas contínuo.

# %%
if "inadim" in dados_estudo:
    # 1. Classificação financeira simplificada baseada no status real atual (PEP 20)
    def classificar_comportamento_caixa_real(row) -> str:
        venc = row['dt_datavencimento']
        baixa = row['dt_databaixa']
        
        # Caso A: Pago no Prazo (Baixado em Dia)
        if pd.notna(baixa) and baixa <= venc:
            return 'Baixado em Dia (No Prazo)'
            
        # Caso B: Pago com Atraso (Baixado em Atraso)
        elif pd.notna(baixa) and baixa > venc:
            return 'Baixado em Atraso (Recuperado)'
            
        # Caso C: Em Aberto Atualmente (Sem data de baixa até hoje)
        else:
            return 'Em Aberto Atualmente (Sem Baixa)'

    # Aplica a nova classificação simplificada
    df_analise['categoria_caixa'] = df_analise.apply(classificar_comportamento_caixa_real, axis=1)

    # 2. Montagem da Linha do Tempo Contínua (Ordenação cronológica contínua de 18 meses)
    df_analise['periodo_ordenado'] = df_analise['ano_venc'] * 100 + df_analise['mes_venc']
    df_analise['periodo_nome'] = df_analise['mes_venc'].astype(str) + "/" + df_analise['ano_venc'].astype(str)

    # Agrupa e soma os valores por período contínuo e categoria de caixa
    df_consolidado_linha = df_analise.groupby(['periodo_ordenado', 'periodo_nome', 'categoria_caixa'])['vl_valororiginal'].sum().reset_index()

    # Pivota para estruturar as 3 categorias em colunas lado a lado
    df_linha_tempo = df_consolidado_linha.pivot(
        index=['periodo_ordenado', 'periodo_nome'],
        columns='categoria_caixa',
        values='vl_valororiginal'
    ).fillna(0.0).reset_index()

    # Ordena cronologicamente
    df_linha_tempo = df_linha_tempo.sort_values(by='periodo_ordenado')

    # Blindagem de colunas para evitar KeyErrors
    for col in ['Baixado em Dia (No Prazo)', 'Baixado em Atraso (Recuperado)', 'Em Aberto Atualmente (Sem Baixa)']:
        if col not in df_linha_tempo.columns:
            df_linha_tempo[col] = 0.0

    print("=== TABELA 7: SÉRIE TEMPORAL CONTÍNUA DE COMPORTAMENTO DE CAIXA REAL (2025/2026) ===")
    display(df_linha_tempo[['periodo_nome', 'Baixado em Dia (No Prazo)', 'Baixado em Atraso (Recuperado)', 'Em Aberto Atualmente (Sem Baixa)']])

    # 3. GERAÇÃO DO GRÁFICO CONTÍNUO DE SÉRIE HISTÓRICA REAL (Line Plot)
    plt.figure(figsize=(14, 6))
    sns.set_theme(style="whitegrid")

    df_grafico_linha = df_linha_tempo.set_index('periodo_nome')

    # Plota as três linhas de fluxo de caixa real com alto contraste
    plt.plot(df_grafico_linha.index, df_grafico_linha['Baixado em Dia (No Prazo)'], marker='o', linewidth=2.5, color='#2ca02c', label='Baixado em Dia (No Prazo)')
    plt.plot(df_grafico_linha.index, df_grafico_linha['Baixado em Atraso (Recuperado)'], marker='o', linewidth=2.5, color='#D97706', label='Baixado em Atraso (Recuperado)')
    plt.plot(df_grafico_linha.index, df_grafico_linha['Em Aberto Atualmente (Sem Baixa)'], marker='s', linewidth=2.5, color='#d62728', label='Em Aberto Atualmente (Risco/Sem Baixa)')

    # Formatador dinâmico do eixo Y para moeda (Evita notação científica)
    f_financeiro = ticker.FuncFormatter(
        lambda x, pos: f'R$ {x/1e6:.1f}M' if x >= 1e6 else f'R$ {x/1e3:.0f}K' if x >= 1e3 else f'R$ {x:.0f}'
    )
    plt.gca().yaxis.set_major_formatter(f_financeiro)

    # Ajustes estéticos finais
    plt.title("Evolução Histórica do Caixa Real (Safra Contínua 2025/2026)", fontsize=13, fontweight='bold', pad=12)
    plt.ylabel("Volume Financeiro (R$)", fontsize=11)
    plt.xlabel("Mês / Ano de Vencimento", fontsize=11)
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(title="Situação Atual do Caixa", bbox_to_anchor=(1.01, 1), loc='upper left')
    
    plt.tight_layout()
    plt.show()
# %% [markdown]
# ## 8. Consolidação da Linha do Tempo por QUANTIDADE DE PARCELAS (2025/2026)
# Consolida os 18 meses de série histórica contínua de quantidade física de parcelas emitida,
# mapeando as três categorias reais de comportamento de pagamento e plota a evolução em linhas.

# %%
if "inadim" in dados_estudo:
    # 1. Agrupa e conta a quantidade física de parcelas (cdg_idlan) por período e comportamento de caixa
    df_consolidado_linha_qtd = df_analise.groupby(
        ['periodo_ordenado', 'periodo_nome', 'categoria_caixa']
    )['cdg_idlan'].count().reset_index()

    # 2. Pivota para estruturar as 3 categorias em colunas lado a lado (Contagem de Linhas)
    df_linha_tempo_qtd = df_consolidado_linha_qtd.pivot(
        index=['periodo_ordenado', 'periodo_nome'],
        columns='categoria_caixa',
        values='cdg_idlan'
    ).fillna(0.0).reset_index()

    # Ordena cronologicamente
    df_linha_tempo_qtd = df_linha_tempo_qtd.sort_values(by='periodo_ordenado')

    # Blindagem de colunas para contagem
    for col in ['Baixado em Dia (No Prazo)', 'Baixado em Atraso (Recuperado)', 'Em Aberto Atualmente (Sem Baixa)']:
        if col not in df_linha_tempo_qtd.columns:
            df_linha_tempo_qtd[col] = 0.0

    print("=== TABELA 8: SÉRIE TEMPORAL CONTÍNUA POR QUANTIDADE DE PARCELAS REAL (2025/2026) ===")
    display(df_linha_tempo_qtd[['periodo_nome', 'Baixado em Dia (No Prazo)', 'Baixado em Atraso (Recuperado)', 'Em Aberto Atualmente (Sem Baixa)']])

    # 3. GERAÇÃO DO GRÁFICO CONTÍNUO DE QUANTIDADE (Line Plot)
    plt.figure(figsize=(14, 6))
    sns.set_theme(style="whitegrid")

    df_grafico_linha_qtd = df_linha_tempo_qtd.set_index('periodo_nome')

    # Plota as três linhas de contagem com cores correspondentes às da seção financeira
    plt.plot(df_grafico_linha_qtd.index, df_grafico_linha_qtd['Baixado em Dia (No Prazo)'], marker='o', linewidth=2.5, color='#2ca02c', label='Baixado em Dia (No Prazo)')
    plt.plot(df_grafico_linha_qtd.index, df_grafico_linha_qtd['Baixado em Atraso (Recuperado)'], marker='o', linewidth=2.5, color='#D97706', label='Baixado em Atraso (Recuperado)')
    plt.plot(df_grafico_linha_qtd.index, df_grafico_linha_qtd['Em Aberto Atualmente (Sem Baixa)'], marker='s', linewidth=2.5, color='#d62728', label='Em Aberto Atualmente (Risco/Sem Baixa)')

    # Exibe o eixo Y como inteiro comum (Contagem física de boletos)
    plt.gca().yaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))

    # Ajustes estéticos finais
    plt.title("Evolução Histórica da Quantidade Física de Parcelas (Safra Contínua 2025/2026)", fontsize=13, fontweight='bold', pad=12)
    plt.ylabel("Quantidade de Parcelas (Unidades)", fontsize=11)
    plt.xlabel("Mês / Ano de Vencimento", fontsize=11)
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend(title="Situação Atual das Parcelas", bbox_to_anchor=(1.01, 1), loc='upper left')
    
    plt.tight_layout()
    plt.show()
