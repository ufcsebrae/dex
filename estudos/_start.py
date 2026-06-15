#%%
import pandas as pd
from sqlalchemy import create_engine
import urllib

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

# 2. Queries
query_fechamento = "SELECT * FROM [DEX-FATOFECHAMENTO] WHERE [NM_DATA] >= '2025-01-01' and nm_descnvl1 like 'Desp%'"
query_planejado = "SELECT * FROM [DEX-plancc]"

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
# Primeiro, extraímos os 7 primeiros caracteres da conta
df_1['nm_conta_7dig'] = df_1['nm_conta'].str[0:7]

# Segundo, aplicamos o De/Para para criar a chave perfeita de cruzamento
df_1['chave_para_merge'] = (
    df_1['nm_conta_7dig']
    .map(de_para_contas)
    .fillna(df_1['nm_conta_7dig'])
)

# 5. O Merge Real com TODOS OS CAMPOS
# Cruzamos o df_1 (completo) com o df_2 (completo)
df_ajuste = df_1.merge(
    df_2, 
    left_on='chave_para_merge', 
    right_on='cdg_natorcamentonvl4', 
    how='left'
)

df_ajuste = df_ajuste.drop(columns=['nm_conta_7dig', 'chave_para_merge'])
print(df_ajuste.head(100))
# %%