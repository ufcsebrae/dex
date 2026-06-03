"""Módulo responsável pela construção das Entidades de Domínio e infraestrutura (PEP 257)."""

import json
import os
import asyncio
import copy
import threading
from pathlib import Path
from itertools import chain
import pandas as pd
from dotenv import load_dotenv

from logger import configura_logger
from extract.config.config import OrigemConfig, SetaDF

log = configura_logger(__name__)
load_dotenv()

# Variáveis para inicialização segura do OLAP
olap_initialized = False
olap_init_lock = threading.Lock()


def carregar_mapa_queries(caminho_arquivo: Path) -> dict[str, str]:
    """
    Carrega o mapeamento entre os arquivos de queries e suas respectivas conexões.
    Se o arquivo JSON não existir, ele é gerado automaticamente com os valores padrão (PEP 20).
    """
    mapeamentos_padrao = {
        "fatofechamento": "SPSVSQL39_HubDados",
        "inadim": "SPSVSQL39_HubDados",
        "plancc": "SPSVSQL39_HubDados",
        "orcado": "OLAP_SME",
        "orcado_receitas": "OLAP_SME",
        "orcado_receitas_cenario": "OLAP_SME",
        "fatoajustadonacional": "AZURE",
        "metareceita": "AZURE"
    }

    if not caminho_arquivo.exists():
        try:
            caminho_arquivo.write_text(json.dumps(mapeamentos_padrao, indent=4), encoding="utf-8")
            log.info(f"Arquivo de mapeamento declarative criado automaticamente em: {caminho_arquivo}")
            return mapeamentos_padrao
        except Exception as e:
            log.error(f"Não foi possível persistir o arquivo de mapeamento {caminho_arquivo}: {e}")
            return mapeamentos_padrao

    try:
        conteudo = caminho_arquivo.read_text(encoding="utf-8")
        mapa = json.loads(conteudo)
        return {str(k).lower().strip(): str(v).strip() for k, v in mapa.items()}
    except Exception as e:
        log.error(f"Falha ao interpretar {caminho_arquivo}. Usando mapeamento em memória. Erro: {e}")
        return mapeamentos_padrao


def carregar_queries_locais(caminho_pasta: Path) -> dict[str, str]:
    """Varre um diretório buscando arquivos .sql e .mdx e retorna o seu conteúdo mapeado."""
    if not isinstance(caminho_pasta, Path):
        caminho_pasta = Path(caminho_pasta)

    if not caminho_pasta.is_dir():
        log.warning(f"O diretório de queries não foi encontrado: {caminho_pasta}")
        return {}

    dicionario_queries: dict[str, str] = {}
    arquivos_suportados = chain(caminho_pasta.glob("*.sql"), caminho_pasta.glob("*.mdx"))

    for arquivo in arquivos_suportados:
        if arquivo.name.startswith("."):
            continue

        try:
            try:
                conteudo = arquivo.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                log.warning(f"Falha ao ler {arquivo.name} em UTF-8. Tentando 'latin-1'.")
                conteudo = arquivo.read_text(encoding="latin-1")

            nome_query = arquivo.stem.lower()
            dicionario_queries[nome_query] = conteudo
            log.info(f"Query loaded com sucesso: {arquivo.name} -> chave '{nome_query}'")
        except Exception as erro_leitura:
            log.error(f"Falha crítica ao ler o arquivo {arquivo.name}: {erro_leitura}", exc_info=True)

    return dicionario_queries


def cria_mapa_origens_config() -> dict[str, OrigemConfig]:
    """Lê o .env e retorna um dicionário de Value Objects de infraestrutura."""
    configs_env = os.getenv("CONEXOES", "[]")
    if not configs_env:
        return {}

    configs_env = configs_env.strip().strip("'").strip('"')
    if not configs_env or configs_env == "[]":
        return {}

    try:
        catalogo = json.loads(configs_env)[0]
    except Exception as e:
        log.error(f"Erro ao decodificar JSON do .env: {e}")
        return {}
        
    mapa_origens = {}
    for nome, detalhes in catalogo.items():
        tipo_db = detalhes.get("tipo", "")
        str_conn = ""
        if tipo_db == "olap":
            str_conn = detalhes.get("str_conexao", "")
        elif tipo_db == "azure_sql":
            str_conn = (
                f"Driver={{{detalhes.get('driver')}}};"
                f"Server={detalhes.get('servidor')};"
                f"Database={detalhes.get('banco')};"
                f"Authentication={detalhes.get('authentication')};"
                f"TrustServerCertificate=yes;"
            )
        elif tipo_db == "sql":
            trusted = "yes" if detalhes.get("trusted_connection") else "no"
            str_conn = (
                f"Driver={{{detalhes.get('driver')}}};"
                f"Server={detalhes.get('servidor')};"
                f"Database={detalhes.get('banco')};"
                f"Trusted_Connection={trusted};"
                f"TrustServerCertificate=yes;"
            )
        
        try:
            config_objeto = OrigemConfig(
                nome_processo=nome,
                tipo=tipo_db,
                database=detalhes.get("banco"),
                servidor=detalhes.get("servidor"),
                driver=detalhes.get("driver"),
                string_connection=str_conn
            )
            mapa_origens[nome] = config_objeto
        except Exception as e:
            log.error(f"Falha de validação OrigemConfig para {nome}: {e}")
            
    return mapa_origens


async def buscar_dados() -> list[SetaDF]:
    """
    Constrói a linhagem unindo queries e configurações.
    Gera uma Entidade (SetaDF) independente para cada query encontrada.
    """
    mapa_conexoes = cria_mapa_origens_config()
    if not mapa_conexoes:
        log.warning("Nenhuma configuração base de conexões carregada do .env.")
        return []
    
    caminho_mapa_queries = Path(__file__).parent / "mapa_queries.json"
    de_para_query_conexao = carregar_mapa_queries(caminho_mapa_queries)
    
    caminho_pasta_queries = Path(__file__).parent / "queries"
    dicionario_queries = carregar_queries_locais(caminho_pasta_queries)
    
    entidades_preparadas = []
    
    for nome_query, string_query in dicionario_queries.items():
        nome_conexao_alvo = de_para_query_conexao.get(nome_query)
        
        if not nome_conexao_alvo or nome_conexao_alvo not in mapa_conexoes:
            log.warning(f"A query '{nome_query}' não tem uma conexão alvo mapeada em mapa_queries.json. Ignorando.")
            continue
            
        origem_alvo = copy.deepcopy(mapa_conexoes[nome_conexao_alvo])
        origem_alvo.nome_processo = nome_query
        entidade_dado = SetaDF(origem=origem_alvo, query=string_query)
        entidades_preparadas.append(entidade_dado)
        
    return entidades_preparadas


def consulta_sql(query: str, string_connection: str) -> pd.DataFrame:
    """
    Extrai dados de bancos relacionais de forma extremamente robusta.
    
    Suporta scripts complexos com múltiplos blocos (Stored Procedures, tabelas temporárias, 
    declarações de variáveis) percorrendo sequencialmente todos os result sets usando 
    `cursor.nextset()` até localizar o SELECT real de dados (PEP 20, PEP 257).
    """
    import pyodbc
    
    query_limpa = query.strip()
    if not query_limpa.lower().startswith("set nocount on"):
        query_limpa = f"SET NOCOUNT ON;\n{query_limpa}"
        
    conexao = pyodbc.connect(string_connection)
    try:
        cursor = conexao.cursor()
        cursor.execute(query_limpa)
        
        # Pula conjuntos vazios/afetados gerados pelos múltiplos INSERT INTO #temp
        while cursor.description is None:
            if not cursor.nextset():
                break
                
        if cursor.description is not None:
            colunas = [col[0] for col in cursor.description]
            dados = cursor.fetchall()
            df = pd.DataFrame.from_records(dados, columns=colunas)
        else:
            log.warning("O script SQL executou com sucesso, mas nenhum SELECT de retorno foi localizado.")
            df = pd.DataFrame()
            
    except Exception as e:
        log.error(f"Erro de processamento no cursor de banco de dados: {e}")
        raise
    finally:
        conexao.close()
        
    return df


def consulta_olap(query: str, string_connection: str) -> pd.DataFrame:
    """Extrai dados de cubos via pyadomd, com inicialização segura e centralizada do ambiente .NET."""
    import os
    import sys
    
    global olap_initialized
    
    if not olap_initialized:
        with olap_init_lock:
            if not olap_initialized:
                log.info("Executando a inicialização do ambiente OLAP pela primeira vez...")
                
                gateway_path = r"C:\Program Files\On-premises data gateway"
                if not os.path.exists(gateway_path):
                    raise FileNotFoundError(f"Diretório do 'On-premises data gateway' não encontrado em '{gateway_path}'.")

                if gateway_path not in sys.path:
                    sys.path.append(gateway_path)

                try:
                    import clr
                    clr.AddReference("Microsoft.AnalysisServices.AdomdClient")
                    log.info("Referência 'Microsoft.AnalysisServices.AdomdClient' carregada com sucesso.")
                    olap_initialized = True
                except Exception as erro_clr:
                    raise RuntimeError(f"FALHA crítica ao carregar a DLL via CLR. Erro: {erro_clr}")

    try:
        from pyadomd import Pyadomd
    except ImportError as erro_import:
        raise ImportError(f"Falha ao importar 'pyadomd'. Verifique a instalação. Erro: {erro_import}")
        
    log.info(f"Conectando ao cubo OLAP com a string: '{string_connection}'")
    with Pyadomd(string_connection) as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(query)
            colunas = [info_coluna[0] for info_coluna in cursor.description]
            dados = cursor.fetchall()
            
    log.info(f"Consulta ao cubo OLAP concluída, {len(dados)} registros retornados.")
    return pd.DataFrame.from_records(dados, columns=colunas)


async def extrair_dataframe_da_origem(entidade: SetaDF) -> SetaDF:
    """Executa a extração em banco de dados e mutaciona o estado da entidade."""
    log.info(f"Conectando ao banco para extrair: {entidade.origem.nome_processo}")
    try:
        if entidade.origem.tipo in ["sql", "azure_sql"]:
            df = await asyncio.to_thread(consulta_sql, entidade.query, entidade.origem.string_connection)
        elif entidade.origem.tipo == "olap":
            df = await asyncio.to_thread(consulta_olap, entidade.query, entidade.origem.string_connection)
        else:
            log.error(f"Engine não suportada: {entidade.origem.tipo}")
            return entidade
            
        entidade.df = df
        return entidade
    except Exception as e:
        log.error(f"Falha na extração para {entidade.origem.nome_processo}: {e}")
        return entidade
