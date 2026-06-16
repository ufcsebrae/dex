# %%
import pandas as pd
from sqlalchemy import create_engine
import urllib
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

# 1. Conexão com o Banco de Dados
parametros_odbc: str = (
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server=spsvsql39;"
    f"Database=FINANCA;"
    f"Trusted_Connection=yes;"
    f"Encrypt=no;"
    f"TrustServerCertificate=yes;"
)
params = urllib.parse.quote_plus(parametros_odbc)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# 2. Queries (Nova query de fechamento integrada com a CTE)
query_fechamento = """
WITH FECHAMENTO AS (
    SELECT 
        CASE 
            WHEN YEAR(NM_DATA) = 2025 THEN 'PPA 2025 - 2025/Jun'
            WHEN YEAR(NM_DATA) = 2026 THEN 'PPA 2026 - 2026/Jun' 
            ELSE NULL 
        END AS nm_ppa,
        nm_unidade,
        nm_projeto AS nm_iniciativa,
        nm_acao,
        LEFT(nm_conta, 7) AS cdg_natorcamentonvl4,
        CASE 
            WHEN YEAR(NM_DATA) = 2025 THEN '2025'
            WHEN YEAR(NM_DATA) = 2026 THEN '2026' 
            ELSE NULL 
        END AS vl_ano,
        MONTH(NM_DATA) AS vl_mes,
        nm_cc,
        vl_valor
    FROM [DEX-FATOFECHAMENTO]
    WHERE YEAR([NM_DATA]) IN ('2025', '2026') 
      AND MONTH(NM_DATA) <= 6 
      AND nm_descnvl1 IN ('DESPESAS','DESPESAS EXCLUSIVAS DO ORÇAMENTO')
),
GRUPO AS (
    SELECT 
        nm_ppa,
        nm_unidade,
        nm_iniciativa,
        nm_acao,
        cdg_natorcamentonvl4,
        nm_cc,
        vl_ano,
        vl_mes,
        SUM(VL_VALOR) AS vl_valor  
    FROM FECHAMENTO
    GROUP BY nm_ppa, nm_unidade, nm_iniciativa, nm_acao, cdg_natorcamentonvl4, nm_cc, vl_ano, vl_mes
)
SELECT * FROM GRUPO
"""
query_planejado = """SELECT * FROM [DEX-plancc]"""

# Carrega os DataFrames
df_1 = pd.read_sql_query(query_fechamento, engine)
df_2 = pd.read_sql_query(query_planejado, engine)

# --- TRATAMENTO DOS DADOS PARA O MERGE COMPLETO ---

# 3. Tabela hardcoded de De/Para
de_para_contas = {
    "5.2.2.2": "5.1.2.2",
    "5.2.4.1": "5.1.4.1",
    "5.2.1.1": "5.1.1.1",
    "5.2.2.1": "5.1.2.1",
    "5.2.3.1": "5.1.2.1",
    "5.2.5.3": "5.1.5.2",
    "5.2.5.2": "5.1.5.2",
    "5.1.1.2": "5.1.1.1"
}

# 4. Tratamos o df_1 mantendo TODAS as colunas originais
# Como a nova query já traz o 'cdg_natorcamentonvl4' com os 7 dígitos da conta,
# usamos ele diretamente para gerar a chave de merge.
df_1['chave_para_merge'] = (
    df_1['cdg_natorcamentonvl4']
    .map(de_para_contas)
    .fillna(df_1['cdg_natorcamentonvl4'])
)
df_1['vl_mes'] = df_1['vl_mes'].astype(str)
df_2['vl_mes'] = df_2['vl_mes'].astype(str)

# 5. O Merge Real
df_ajuste = df_1.merge(
    df_2, 
    left_on=['nm_cc','chave_para_merge','vl_ano','vl_mes','nm_ppa'],
    right_on=['nm_cc','cdg_natorcamentonvl4','vl_ano','vl_mes','nm_ppa'],
    how='left',
    suffixes=('', '_df2') # Evita conflito se houver colunas com mesmo nome em ambos
)

# Removemos a chave auxiliar temporária
df_ajuste = df_ajuste.drop(columns=['chave_para_merge'])

df_final = df_ajuste[['nm_ppa', 'nm_unidade', 'nm_iniciativa', 'nm_acao', 'cdg_natorcamentonvl4', 'nm_cc', 'vl_ano', 'vl_mes', 'vl_valor', 'vl_ajustado']].head()
# %%
print(df_final[df_final['vl_ano'] == '2025']['vl_ajustado'].mean())
#%%
print(df_final[df_final['vl_ano'] == '2026']['vl_ajustado'].mean())
# %%
print(df_final['vl_ano'] == '2026'])
#%%
print(df_final['vl_ano'] == '2025'])


# %%
