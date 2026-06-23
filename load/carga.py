"""Módulo responsável pela etapa de Carga (Load) do pipeline ETL (PEP 257)."""

from __future__ import annotations

import os
import json
import asyncio
import urllib.parse
import re
import pandas as pd
from datetime import datetime
from typing import Callable
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from logger import configura_logger

log = configura_logger(__name__)


def _sanitizar_json_env(json_str: str) -> str:
    """
    Sanitiza strings JSON contendo contra-barras inválidas de forma inteligente.

    Esta função identifica escapes JSON válidos (como \\, \", \n) e os preserva.
    Qualquer contra-barra simples solta (comum em caminhos de rede e instâncias SQL)
    é convertida de forma segura para barra dupla (\\) (PEP 257).

    :param json_str: String JSON original bruta obtida do ambiente.
    :type json_str: str
    :return: String JSON com as sequências de escape tratadas.
    :rtype: str
    """
    # Expressão que casa com escapes válidos em um grupo de captura ou encontra barras órfãs
    padrao_escape_inteligente = re.compile(
        r'(\\["\\/bfnrt]|\\u[0-9a-fA-F]{4})|\\'
    )
    # Se capturar um escape legítimo, mantém. Caso contrário, duplica a barra simples
    return padrao_escape_inteligente.sub(
        lambda m: m.group(1) if m.group(1) else r"\\", 
        json_str
    )


def _obter_string_conexao_financa() -> str:
    """
    Analisa a variável de ambiente 'CONEXOES' em JSON e monta a string 
    de conexão SQLAlchemy para o banco FINANCA.
    """
    conexoes_env: str | None = os.getenv("CONEXOES")
    
    if not conexoes_env:
        erro_msg: str = "Variável de ambiente 'CONEXOES' ausente. Carga abortada."
        log.error(erro_msg)
        raise ValueError(erro_msg)

    try:
        # Sanitização robusta contra barras invertidas do driver no arquivo .env
        conexoes_env_sanitizado = _sanitizar_json_env(conexoes_env)
        conexoes_lista: list[dict[str, dict[str, Any]]] = json.loads(conexoes_env_sanitizado)
    except json.JSONDecodeError as erro_json:
        log.error(f"Falha ao decodificar a variável 'CONEXOES': {erro_json}")
        raise ValueError(f"Formato JSON inválido na variável 'CONEXOES': {erro_json}")

    if not conexoes_lista:
        raise ValueError("A lista de conexões na variável 'CONEXOES' está vazia.")

    # O JSON possui uma lista com um único dicionário contendo as chaves dos servidores
    dic_conexoes: dict[str, dict[str, Any]] = conexoes_lista[0]
    config_alvo: dict[str, Any] | None = None
    
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
    on_progress: Callable[[int], None] | None = None
) -> None:
    """
    Carrega o DataFrame processado no banco de dados de destino de forma fragmentada.
    
    Aplica política de chunks dinâmicos, converte decimais para float64 em memória 
    para garantir velocidade extrema, força fisicamente o tipo DECIMAL(38, 8) no SQL Server,
    mapeia anos/meses como INTEGER e atualiza o progresso de forma thread-safe.
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
    
    # Com a otimização de floats, podemos usar blocos maiores sem medo de estourar a rede!
    chunk_size: int = max(5000, min(20000, 200000 // colunas_count))
    num_chunks: int = (total_linhas + chunk_size - 1) // chunk_size
    
    log.info(f"Carga otimizada para {schema_banco}.{nome_tabela_final}: {total_linhas} linhas em {num_chunks} blocos (tamanho do bloco: {chunk_size})")

    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()

    # --- MAPEAMENTO DINÂMICO E CONVERSÃO EM MEMÓRIA ---
    from sqlalchemy.types import Numeric, Integer
    import decimal

    # Define as colunas que iniciam com 'vl_' mas que NÃO devem ser decimais (são inteiros)
    EXCLUSOES_INTEIROS = {"vl_ano", "vl_mes"}

    mapa_dtypes = {}
    for col in df.columns:
        # CORREÇÃO: Força o tipo físico como INTEGER no SQL Server para as colunas temporais
        if col in EXCLUSOES_INTEIROS:
            mapa_dtypes[col] = Integer()
            continue
            
        # Se for uma coluna de valores monetários (prefixo 'vl_')
        if col.startswith('vl_'):
            non_nulls = df[col].dropna()
            if not non_nulls.empty:
                primeiro_val = non_nulls.iloc[0]
                # Se for decimal.Decimal, convertemos em memória para float64 (evita o bug 10054 do TDS)
                if isinstance(primeiro_val, decimal.Decimal):
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                
                # Forçamos o banco a criar a coluna de valores fisicamente como DECIMAL(38, 8)
                mapa_dtypes[col] = Numeric(38, 8)

    def _executa_carga_sync() -> None:
        """Operação síncrona de I/O executada no thread-pool (PEP 20)."""
        engine: Engine = create_engine(string_conexao, fast_executemany=True)
        
        try:
            # Passo 1: Cria apenas a estrutura física da tabela vazia com os tipos corrigidos
            df.head(0).to_sql(
                name=nome_tabela_final,
                con=engine,
                schema=schema_banco,
                if_exists="replace",
                index=False,
                dtype=mapa_dtypes
            )
            
            # Passo 2: Abre uma transação única explícita na mesma conexão
            with engine.begin() as conexao:
                for i in range(num_chunks):
                    lote_df = df.iloc[i * chunk_size : (i + 1) * chunk_size]
                    
                    lote_df.to_sql(
                        name=nome_tabela_final,
                        con=conexao,
                        schema=schema_banco,
                        if_exists="append",
                        index=False
                    )
                    
                    porcentagem_concluida = int(((i + 1) / num_chunks) * 100)
                    if on_progress:
                        loop.call_soon_threadsafe(on_progress, porcentagem_concluida)
                        
            log.info(f"Carga fragmentada concluída com sucesso na tabela {schema_banco}.{nome_tabela_final}.")
        except Exception as e:
            log.error(f"Falha de banco de dados durante a carga fracionada de {nome_tabela_final}: {e}", exc_info=True)
            raise

    await loop.run_in_executor(None, _executa_carga_sync)


    def _executa_carga_sync() -> None:
        """Operação síncrona de I/O executada no thread-pool (PEP 20)."""
        engine: Engine = create_engine(string_conexao, fast_executemany=True)
        
        try:
            # Passo 1: Cria apenas a estrutura física da tabela vazia com tipos explícitos
            df.head(0).to_sql(
                name=nome_tabela_final,
                con=engine,
                schema=schema_banco,
                if_exists="replace",
                index=False,
                dtype=mapa_dtypes
            )
            
            # Passo 2: Abre uma transação única explícita na mesma conexão
            with engine.begin() as conexao:
                for i in range(num_chunks):
                    lote_df = df.iloc[i * chunk_size : (i + 1) * chunk_size]
                    
                    lote_df.to_sql(
                        name=nome_tabela_final,
                        con=conexao,
                        schema=schema_banco,
                        if_exists="append",
                        index=False
                    )
                    
                    porcentagem_concluida = int(((i + 1) / num_chunks) * 100)
                    if on_progress:
                        loop.call_soon_threadsafe(on_progress, porcentagem_concluida)
                        
            log.info(f"Carga fragmentada concluída com sucesso na tabela {schema_banco}.{nome_tabela_final}.")
        except Exception as e:
            log.error(f"Falha de banco de dados durante a carga fracionada de {nome_tabela_final}: {e}", exc_info=True)
            raise

    await loop.run_in_executor(None, _executa_carga_sync)

    def _executa_carga_sync() -> None:
        """Operação síncrona de I/O em chunks executada no thread-pool (PEP 20)."""
        # CORREÇÃO: Criação da engine aplicando 'fast_executemany' diretamente de forma efetiva
        engine: Engine = create_engine(string_conexao, fast_executemany=True)
        
        try:
            # Passo 1: Cria a estrutura física da tabela definindo explicitamente os tipos numéricos
            df.head(0).to_sql(
                name=nome_tabela_final,
                con=engine,
                schema=schema_banco,
                if_exists="replace",
                index=False,
                dtype=mapa_dtypes  # Define explicitamente tipos decimais com escala
            )
            
            # Passo 2: Abre uma transação única explícita na mesma conexão
            # Se algum lote falhar, o bloco realiza o rollback completo automaticamente
            with engine.begin() as conexao:
                for i in range(num_chunks):
                    lote_df = df.iloc[i * chunk_size : (i + 1) * chunk_size]
                    
                    lote_df.to_sql(
                        name=nome_tabela_final,
                        con=conexao,  # CORREÇÃO: Utiliza a conexão transacionada ativa
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
            # CORREÇÃO: Exibe o rastreamento completo e a causa raiz real do erro de banco
            log.error(f"Falha de banco de dados durante a carga fracionada de {nome_tabela_final}: {e}", exc_info=True)
            raise

    await loop.run_in_executor(None, _executa_carga_sync)



async def salva_metricas(metricas: dict[str, Any], nome_processo: str) -> None:
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
            # CORREÇÃO: Habilitação explícita do fast_executemany
            engine: Engine = create_engine(string_conexao, fast_executemany=True)
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
