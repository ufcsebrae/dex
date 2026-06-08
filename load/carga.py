"""Módulo responsável pela etapa de Carga (Load) do pipeline ETL (PEP 257)."""

import os
import json
import asyncio
import urllib.parse
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from logger import configura_logger

log = configura_logger(__name__)


def _obter_string_conexao_financa() -> str:
    """
    Analisa a variável de ambiente 'CONEXOES' em JSON e monta a string 
    de conexão SQLAlchemy para o banco FINANCA.
    """
    conexoes_env: Optional[str] = os.getenv("CONEXOES")
    
    if not conexoes_env:
        erro_msg: str = "Variável de ambiente 'CONEXOES' ausente. Carga abortada."
        log.error(erro_msg)
        raise ValueError(erro_msg)

    try:
        conexoes_lista: List[Dict[str, Dict[str, Any]]] = json.loads(conexoes_env)
    except json.JSONDecodeError as erro_json:
        log.error(f"Falha ao decodificar a variável 'CONEXOES': {erro_json}")
        raise ValueError(f"Formato JSON inválido na variável 'CONEXOES': {erro_json}")

    if not conexoes_lista:
        raise ValueError("A lista de conexões na variável 'CONEXOES' está vazia.")

    # O JSON possui uma lista com um único dicionário contendo as chaves dos servidores
    dic_conexoes: Dict[str, Dict[str, Any]] = conexoes_lista[0]
    config_alvo: Optional[Dict[str, Any]] = None
    
    # Itera para encontrar a configuração que aponta para o banco FINANCA
    for nome_conexao, config in dic_conexoes.items():
        if config.get("banco") == "FINANCA":
            config_alvo = config
            break

    if not config_alvo:
        erro_banco: str = "Configuração para o banco 'FINANCA' não encontrada no JSON."
        log.error(erro_banco)
        raise ValueError(erro_banco)

    servidor: str = config_alvo["servidor"]
    banco: str = config_alvo["banco"]
    driver: str = config_alvo["driver"]

    # Monta os parâmetros ODBC adicionando 'Encrypt=no' e 'TrustServerCertificate=yes'
    # 'Encrypt=no' desativa a criptografia forçada do ODBC Driver 18, solucionando o erro 10054 (PEP 20)
    parametros_odbc: str = (
        f"Driver={{{driver}}};"
        f"Server={servidor};"
        f"Database={banco};"
        f"Trusted_Connection=yes;"
        f"Encrypt=no;"  # CORREÇÃO: Evita falha de handshake TLS/SSL no ODBC Driver 18
        f"TrustServerCertificate=yes;"
    )
    
    # Codifica a string de conexão para passagem segura via URL no SQLAlchemy
    parametros_codificados: str = urllib.parse.quote_plus(parametros_odbc)
    string_conexao_sqlalchemy: str = f"mssql+pyodbc:///?odbc_connect={parametros_codificados}"
    
    return string_conexao_sqlalchemy



async def salva_df(
    df: pd.DataFrame, 
    nome_processo: str, 
    on_progress: Optional[Callable[[int], None]] = None
) -> None:
    """
    Carrega o DataFrame processado no banco de dados de destino de forma fragmentada.
    
    Aplica política de chunks dinâmicos e atualiza o progresso de forma thread-safe (PEP 3156).
    """
    if df is None or df.empty:
        log.warning("DataFrame vazio recebido na camada de carga. Abortando operação.")
        return

    string_conexao: str = _obter_string_conexao_financa()
    
    nome_base_limpo: str = str(nome_processo).strip().lower().replace(" ", "_")
    nome_tabela_final: str = f"dex-{nome_base_limpo}"
    schema_banco: str = "dbo"
    
    total_linhas: int = len(df)
    colunas_count: int = len(df.columns)
    
    # Limita o tamanho do bloco para otimizar velocidade de rede sem estourar parâmetros
    chunk_size: int = max(1000, min(10000, 100000 // colunas_count))
    num_chunks: int = (total_linhas + chunk_size - 1) // chunk_size
    
    log.info(f"Carga fragmentada para {schema_banco}.{nome_tabela_final}: {total_linhas} linhas em {num_chunks} blocos (tamanho do bloco: {chunk_size})")

    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    def _executa_carga_sync() -> None:
        """Operação síncrona de I/O em chunks executada no thread-pool (PEP 20)."""
        try:
            engine: Engine = create_engine(string_conexao)
            engine.execution_options(fast_executemany=True)
            
            # Passo 1: Cria apenas a estrutura física da tabela vazia de forma segura (DDS)
            df.head(0).to_sql(
                name=nome_tabela_final,
                con=engine,
                schema=schema_banco,
                if_exists="replace",
                index=False
            )
            
            # Passo 2: Grava cada lote de dados de forma incremental
            for i in range(num_chunks):
                lote_df = df.iloc[i * chunk_size : (i + 1) * chunk_size]
                
                lote_df.to_sql(
                    name=nome_tabela_final,
                    con=engine,
                    schema=schema_banco,
                    if_exists="append",
                    index=False
                )
                
                # Calcula a porcentagem do lote processado
                porcentagem_concluida = int(((i + 1) / num_chunks) * 100)
                
                # Executa o callback de progresso na thread principal de forma thread-safe
                if on_progress:
                    loop.call_soon_threadsafe(on_progress, porcentagem_concluida)
                    
            log.info(f"Carga fragmentada concluída com sucesso na tabela {schema_banco}.{nome_tabela_final}.")
        except Exception as e:
            log.error(f"Falha de banco de dados durante a carga fracionada: {e}")
            raise

    await loop.run_in_executor(None, _executa_carga_sync)


async def salva_metricas(metricas: Dict[str, Any], nome_processo: str) -> None:
    """
    Salva as métricas geradas pela transformação na tabela centralizada de auditoria.
    """
    if not metricas:
        log.warning("Nenhuma métrica fornecida para gravação.")
        return

    string_conexao: str = _obter_string_conexao_financa()
    schema_banco: str = "dbo"
    nome_tabela_metricas: str = "dex-controle-metricas"

    registro_auditoria = {
        "nome_processo": str(nome_processo),
        "data_execucao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_linhas": int(metricas.get("kpis_gerais", {}).get("total_linhas", 0)),
        "total_colunas": int(metricas.get("kpis_gerais", {}).get("total_colunas", 0)),
        "total_nulos": int(metricas.get("qualidade_dados", {}).get("total_nulos", 0)),
        "detalhes_json": json.dumps(metricas, ensure_ascii=False)
    }

    df_metrica_linha = pd.DataFrame([registro_auditoria])

    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    def _executa_carga_metricas_sync() -> None:
        try:
            engine: Engine = create_engine(string_conexao)
            df_metrica_linha.to_sql(
                name=nome_tabela_metricas,
                con=engine,
                schema=schema_banco,
                if_exists="append",
                index=False
            )
            log.info(f"Métricas gravadas no painel histórico: {schema_banco}.{nome_tabela_metricas}.")
        except Exception as e:
            log.error(f"Falha ao persistir as métricas de auditoria: {e}")
            raise

    await loop.run_in_executor(None, _executa_carga_metricas_sync)


def ler_tabela_carregada(nome_processo: str) -> pd.DataFrame:
    """
    Busca de forma síncrona todos os registros da tabela correspondente 
    no banco de dados de destino 'FINANCA'.
    """
    string_conexao = _obter_string_conexao_financa()
    nome_base_limpo = str(nome_processo).strip().lower().replace(" ", "_")
    nome_tabela_final = f"dex-{nome_base_limpo}"
    schema_banco = "dbo"
    
    query = f"SELECT * FROM {schema_banco}.[{nome_tabela_final}]"
    engine = create_engine(string_conexao)
    
    log.info(f"Buscando dados históricos da tabela de carga: {schema_banco}.[{nome_tabela_final}]")
    try:
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        log.error(f"Tabela {schema_banco}.{nome_tabela_final} não encontrada no banco ou falha na leitura: {e}")
        return pd.DataFrame()
