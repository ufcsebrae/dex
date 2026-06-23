"""API Local do DEX utilizando FastAPI para consumo de dados estruturados e de cobertura anual (PEP 257)."""

import os
import json
import urllib.parse
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

app = FastAPI(title="DEX Secure Local API")

# Habilita CORS para conexão com o frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _obter_string_conexao_financa() -> str:
    """Busca a string de conexão configurada nas variáveis de ambiente do projeto."""
    conexoes_env = os.getenv("CONEXOES")
    if not conexoes_env:
        raise ValueError("Variável de ambiente 'CONEXOES' ausente no arquivo .env.")
        
    conexoes_lista = json.loads(conexoes_env)[0]
    config_alvo = None
    for _, config in conexoes_lista.items():
        if config.get("banco") == "FINANCA":
            config_alvo = config
            break
            
    if not config_alvo:
        raise ValueError("Configuração para o banco 'FINANCA' não encontrada.")

    parametros_odbc = (
        f"Driver={{{config_alvo['driver']}}};"
        f"Server={config_alvo['servidor']};"
        f"Database={config_alvo['banco']};"
        f"Trusted_Connection=yes;"
        f"Encrypt=no;"
        f"TrustServerCertificate=yes;"
    )
    parametros_codificados = urllib.parse.quote_plus(parametros_odbc)
    return f"mssql+pyodbc:///?odbc_connect={parametros_codificados}"


@app.get("/api/planejado-executado")
def obter_planejado_executado():
    """Executa a query unificada de fechamento e gera o payload consolidado de meses, naturezas e projetos."""
    try:
        string_conexao = _obter_string_conexao_financa()
        engine = create_engine(string_conexao)
        
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
                    WHEN YEAR(NM_DATA) = 2025 THEN 2025
                    WHEN YEAR(NM_DATA) = 2026 THEN 2026 
                    ELSE NULL 
                END AS vl_ano,
                MONTH(NM_DATA) AS vl_mes,
                nm_cc,
                vl_valor
            FROM [DEX-FATOFECHAMENTO]
            WHERE YEAR([NM_DATA]) IN (2025, 2026) 
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
            GROUP BY nm_ppa, nm_unidade, nm_iniciativa, nm_acao, cdg_natorcamentonvl4, [nm_descnvl4], nm_cc, vl_ano, vl_mes
        ),
        PLANEJADO AS (
            SELECT  vl_ano, vl_mes, nm_iniciativa, nm_acao, nm_unidade, nm_cc, vl_ajustado, 
                    nm_ppa, cdg_natorcamentonvl4, nm_natorcamentonvl4  FROM [dex-plancc]
            WHERE nm_ppa IN ('PPA 2025 - 2025/Mar','PPA 2026 - 2026/Mar') AND vl_mes <= 3
        ),
        CHAVES_COMUNS AS (
            SELECT vl_ano, vl_mes, nm_iniciativa, nm_acao, nm_unidade,  nm_cc , cdg_natorcamentonvl4 FROM PLANEJADO
            UNION
            SELECT vl_ano, vl_mes, nm_iniciativa, nm_acao, nm_unidade, nm_cc , cdg_natorcamentonvl4 FROM EXECUTADO
        ),
        DADOS_COMBINADOS AS (
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
        
        df_final = pd.read_sql_query(query_unificada, engine)
        
        # Agregação 1: Mensal (Página 1)
        df_mensal = df_final.groupby(['nm_unidade', 'vl_ano', 'vl_mes'], as_index=False).agg(
            planejado=('vl_ajustado', 'sum'),
            executado=('vl_valor', 'sum')
        )
        
        # Agregação 2: Natureza (Página 2)
        df_natureza = df_final.groupby(['nm_unidade', 'vl_ano', 'Descricao_Natureza_Orcamentaria'], as_index=False).agg(
            planejado=('vl_ajustado', 'sum'),
            executado=('vl_valor', 'sum')
        )

        # Agregação 3: Projeto (Tabela Página 1)
        df_projeto = df_final.groupby(['nm_unidade', 'nm_iniciativa', 'vl_ano'], as_index=False).agg(
            planejado=('vl_ajustado', 'sum'),
            executado=('vl_valor', 'sum')
        )
        
        return {
            "mensal": df_mensal.to_dict(orient='records'),
            "natureza": df_natureza.to_dict(orient='records'),
            "projeto": df_projeto.to_dict(orient='records')
        }
        
    except Exception as e:
        print(f"\n[ERRO API DE NEGÓCIOS] Falha: {e}\n")
        return {"error": str(e)}


@app.get("/api/cobertura")
def obter_cobertura():
    """Retorna os dados consolidados de Despesa e Receita agrupados por Unidade E Ano (Q1 2025/2026)."""
    try:
        string_conexao = _obter_string_conexao_financa()
        engine = create_engine(string_conexao)
        
        # CORREÇÃO: Agrupamento explícito por Unidade E Ano para permitir comparação YoY
        query_cobertura = """
        WITH despesas AS (
            SELECT 
                nm_unidade, 
                YEAR(nm_data) AS ano,
                SUM(TRY_CAST(vl_valor AS DECIMAL(18,2))) AS despesa
            FROM [dex-fatofechamento]
            WHERE YEAR(nm_data) IN (2025, 2026) 
              AND MONTH(nm_data) <= 3 
              AND nm_descnvl1 LIKE 'desp%'
            GROUP BY nm_unidade, YEAR(nm_data)
        ),
        receitas AS (
            SELECT 
                nm_unidade, 
                YEAR(nm_data) AS ano,
                SUM(TRY_CAST(vl_valor AS DECIMAL(18,2))) AS receita
            FROM [dex-fatofechamento]
            WHERE YEAR(nm_data) IN (2025, 2026) 
              AND MONTH(nm_data) <= 3 
              AND nm_descnvl3 IN ('RECEITAS DE EMPRESAS BENEFICIADAS', 'RECEITAS DE CONVÊNIOS, SUBVENÇÕES E AUXÍLIOS')
            GROUP BY nm_unidade, YEAR(nm_data)
        )
        SELECT 
            COALESCE(a.nm_unidade, b.nm_unidade) AS unidade, 
            COALESCE(a.ano, b.ano) AS ano,
            ISNULL(a.despesa, 0) AS despesa, 
            ISNULL(b.receita, 0) AS receita,
            (ISNULL(b.receita, 0) - ISNULL(a.despesa, 0)) AS resultado_liquido,
            CASE 
                WHEN ISNULL(a.despesa, 0) > 0 THEN (ISNULL(b.receita, 0) / a.despesa) * 100 
                ELSE 0 
            END AS indice_cobertura
        FROM despesas a
        FULL OUTER JOIN receitas b ON a.nm_unidade = b.nm_unidade AND a.ano = b.ano
        ORDER BY unidade, ano
        """
        
        df = pd.read_sql_query(query_cobertura, engine)
        
        payload = []
        for _, row in df.iterrows():
            payload.append({
                "unidade": str(row["unidade"]).strip(),
                "ano": int(row["ano"]),
                "despesa": float(row["despesa"]),
                "receita": float(row["receita"]),
                "resultado_liquido": float(row["resultado_liquido"]),
                "indice_cobertura": float(row["indice_cobertura"])
            })
            
        return payload
    except Exception as e:
        print(f"\n[ERRO API COBERTURA] Falha: {e}\n")
        return {"error": str(e)}


@app.get("/api/telemetria")
def obter_telemetria():
    """Consulta a tabela de auditoria e entrega os dados estruturados de cargas do ETL."""
    try:
        string_conexao = _obter_string_conexao_financa()
        engine = create_engine(string_conexao)
        
        query = "SELECT nome_processo, data_execucao, total_linhas, total_colunas, total_nulos, detalhes_json FROM dbo.[dex-controle-metricas] ORDER BY data_execucao DESC"
        df = pd.read_sql(query, engine)
        
        payload = []
        for _, row in df.iterrows():
            try:
                detalhes = json.loads(row["detalhes_json"])
            except Exception:
                detalhes = {}
                
            payload.append({
                "nome_processo": str(row["nome_processo"]),
                "data_execucao": str(row["data_execucao"]),
                "total_linhas": int(row["total_linhas"]),
                "total_colunas": int(row["total_colunas"]),
                "total_nulos": int(row["total_nulos"]),
                "detalhes": detalhes
            })
            
        return payload
    except Exception as e:
        print(f"\n[ERRO API TELEMETRIA] Falha: {e}\n")
        return {"error": str(e)}
