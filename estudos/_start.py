# %%
import pandas as pd
from sqlalchemy import create_engine
import urllib
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import json

# %%
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

# %%
# 2. Query de fechamento unificada e otimizada (União planejado e executado)
query_unificada = """
WITH FECHAMENTO AS (
    SELECT 
        CASE 
            WHEN YEAR(NM_DATA) = 2025 THEN 'PPA 2025 - 2025/Mar'
            WHEN YEAR(NM_DATA) = 2026 THEN 'PPA 2026 - 2026/Mar' 
            ELSE NULL 
        END AS nm_ppa,
        nm_unidade,
        nm_projeto AS nm_iniciativa,
        nm_acao,
        CASE
            WHEN LEFT(nm_conta, 7) = '5.1.1.2' THEN '5.1.1.1'
            WHEN LEFT(nm_conta, 7) = '5.2.1.1' THEN '5.1.1.1'
            WHEN LEFT(nm_conta, 7) = '5.2.2.1' THEN '5.1.2.1'
            WHEN LEFT(nm_conta, 7) = '5.2.2.2' THEN '5.1.2.2'
            WHEN LEFT(nm_conta, 7) = '5.2.3.1' THEN '5.1.2.1'
            WHEN LEFT(nm_conta, 7) = '5.2.4.1' THEN '5.1.4.1'
            WHEN LEFT(nm_conta, 7) = '5.2.5.2' THEN '5.1.5.2'
            WHEN LEFT(nm_conta, 7) = '5.2.5.3' THEN '5.1.5.2'
            ELSE LEFT(nm_conta, 7)
        END AS cdg_natorcamentonvl4,
        CASE
            WHEN LEFT(nm_conta, 7) = '5.1.1.2' AND [nm_descnvl4] = 'LIBERAÇÕES DE CONVÊNIOS' THEN 'INVESTIMENTOS'
            WHEN LEFT(nm_conta, 7) = '5.2.1.1' AND [nm_descnvl4] = 'PARTICIPAÇÃO EM OUTRAS ENTIDADES' THEN 'INVESTIMENTOS'
            WHEN LEFT(nm_conta, 7) = '5.2.2.1' AND [nm_descnvl4] = 'BENS IMÓVEIS' THEN 'BENS IMÓVEIS'
            WHEN LEFT(nm_conta, 7) = '5.2.2.2' AND [nm_descnvl4] = 'BENS MÓVEIS' THEN 'BENS MÓVEIS'
            WHEN LEFT(nm_conta, 7) = '5.2.3.1' AND [nm_descnvl4] = 'BENS INTANGÍVEIS' THEN 'BENS IMÓVEIS'
            WHEN LEFT(nm_conta, 7) = '5.2.4.1' AND [nm_descnvl4] = 'DEPÓSITOS JUDICIAIS' THEN 'DEPÓSITOS JUDICIAIS'
            WHEN LEFT(nm_conta, 7) = '5.2.5.2' AND [nm_descnvl4] = 'FUNDO M. DE INVEST. EMPRESAS EMERGENTES' THEN 'FUNDO DE EMPRESAS EMERGENTES'
            WHEN LEFT(nm_conta, 7) = '5.2.5.3' AND [nm_descnvl4] = 'GESTÃO DE FUNDOS E PROGRAMA DE CRÉDITOS' THEN 'FUNDO DE EMPRESAS EMERGENTES'
            WHEN LEFT(nm_conta, 7) = '3.1.2.1' AND [nm_descnvl4] = 'SERVIÇOS ESPECIALIZADOS - PJ' THEN 'SERVIÇOS ESPECIALIZADOS'
            WHEN LEFT(nm_conta, 7) = '3.1.2.2' AND [nm_descnvl4] = 'SERVIÇOS CONTRATADOS - PJ' THEN 'SERVIÇOS CONTRATADOS'
            WHEN LEFT(nm_conta, 7) = '3.1.3.1' AND [nm_descnvl4] = 'DESPESAS COM VIAGENS E LOCOMOÇÃO' THEN 'DESPESAS COM VIAGENS'
            WHEN LEFT(nm_conta, 7) = '3.1.3.2' AND [nm_descnvl4] = 'ALUGUÉIS E ENCARGOS - PESSOA JURÍDICA (PJ)' THEN 'ALUGUÉIS E ENCARGOS'
            WHEN LEFT(nm_conta, 7) = '3.1.3.7' AND [nm_descnvl4] = 'DEMAIS CUSTOS E DESPESAS GERAIS - PJ' THEN 'DEMAIS CUSTOS E DESPESAS GERAIS'
            ELSE [nm_descnvl4]
        END AS [nm_descnvl4],
        
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
      AND MONTH(NM_DATA) <= 3 
      AND nm_descnvl1 IN ('DESPESAS','DESPESAS EXCLUSIVAS DO ORÇAMENTO')
),
EXECUTADO AS (
    SELECT 
        nm_ppa,
        nm_unidade,
        nm_iniciativa,
        nm_acao,
        cdg_natorcamentonvl4,
        [nm_descnvl4],
        nm_cc,
        vl_ano,
        vl_mes,
        SUM(VL_VALOR) AS vl_valor  
    FROM FECHAMENTO
    GROUP BY nm_ppa, nm_unidade, nm_iniciativa, nm_acao, cdg_natorcamentonvl4,[nm_descnvl4], nm_cc, vl_ano, vl_mes
)
,PLANEJADO AS (
    SELECT  vl_ano, vl_mes, nm_iniciativa, nm_acao, nm_unidade, nm_cc, vl_ajustado, 
            nm_ppa, cdg_natorcamentonvl4,nm_natorcamentonvl4  FROM [dex-plancc]
    WHERE nm_ppa IN ('PPA 2025 - 2025/Mar','PPA 2026 - 2026/Mar') AND vl_mes <= 3
)
,CHAVES_COMUNS AS (
    SELECT vl_ano, vl_mes, nm_iniciativa, nm_acao, nm_unidade,  nm_cc , cdg_natorcamentonvl4 FROM PLANEJADO
    UNION
    SELECT vl_ano, vl_mes, nm_iniciativa, nm_acao, nm_unidade, nm_cc , cdg_natorcamentonvl4 FROM EXECUTADO
)
,DADOS_COMBINADOS AS (
    SELECT 
        C.vl_ano, C.vl_mes, C.nm_iniciativa, C.nm_acao, C.nm_unidade, C.nm_cc,
        C.cdg_natorcamentonvl4,
        COALESCE(P.nm_natorcamentonvl4, E.[nm_descnvl4]) AS Descricao_Natureza_Original,
        ISNULL(P.vl_ajustado, 0) AS Valor_Planejado,
        ISNULL(E.vl_valor, 0) AS Valor_Executado
    FROM CHAVES_COMUNS C
    LEFT JOIN PLANEJADO P ON C.vl_ano = P.vl_ano AND C.vl_mes = P.vl_mes AND C.nm_iniciativa = P.nm_iniciativa AND C.nm_cc = P.nm_cc AND C.cdg_natorcamentonvl4 = P.cdg_natorcamentonvl4
    LEFT JOIN EXECUTADO E ON C.vl_ano = E.vl_ano AND C.vl_mes = E.vl_mes AND C.nm_iniciativa = E.nm_iniciativa AND C.nm_cc = E.nm_cc AND C.cdg_natorcamentonvl4 = E.cdg_natorcamentonvl4
)
SELECT
    D.vl_ano, D.vl_mes, D.nm_iniciativa, D.nm_acao, D.nm_unidade, D.nm_cc,
    D.cdg_natorcamentonvl4,
    UPPER(D.Descricao_Natureza_Original) AS Descricao_Natureza_Orcamentaria,
    D.Valor_Planejado AS vl_ajustado,
    D.Valor_Executado AS vl_valor
FROM DADOS_COMBINADOS D
"""

# Carrega os dados unificados diretamente do banco
df_final = pd.read_sql_query(query_unificada, engine)

# Agrupando os dados e consolidando as somas de planejado e executado
df_grouped = df_final.groupby(['nm_unidade', 'nm_iniciativa', 'vl_ano'], as_index=False).agg(
    planejado=('vl_ajustado', 'sum'),
    executado=('vl_valor', 'sum')
)

# --- Opção B: Formato Hierárquico (Estruturado: Unidade -> Iniciativa -> Ano) ---
hierarquico_dict = {}
for _, row in df_grouped.iterrows():
    unidade = row['nm_unidade']
    iniciativa = row['nm_iniciativa']
    ano = row['vl_ano']
    
    if unidade not in hierarquico_dict:
        hierarquico_dict[unidade] = {}
        
    if iniciativa not in hierarquico_dict[unidade]:
        hierarquico_dict[unidade][iniciativa] = {}
        
    hierarquico_dict[unidade][iniciativa][ano] = {
        "planejado": float(row['planejado']),
        "executado": float(row['executado'])
    }

json_hierarquico = json.dumps(hierarquico_dict, indent=4, ensure_ascii=False)

print("\n=== PRÉVIA DO JSON HIERÁRQUICO (OPÇÃO B) ===")
print(json_hierarquico[:600])
