"""Módulo responsável pelas transformações dos DataFrames extraídos (PEP 257)."""

import re
import pandas as pd
from typing import Any, Dict, List, Tuple

from logger import configura_logger

log = configura_logger(__name__)

# Dicionário de mapeamento definido como constante (PEP 8)
DICIONARIO_RENOMEACAO: Dict[str, str] = {
    "[ppa].[ppa com fotografia].[descrição de ppa com fotografia].[member_caption]": "nm_ppa",
    "[unidade organizacional de iniciativa].[unidade organizacional de iniciativa].[nome de unidade organizacional de iniciativa].[member_caption]": "nm_unidade",
    "[natureza orçamentária].[código estruturado 4 nível].[código estruturado 4 nível].[member_caption]": "cdg_natOrcamentoNvl4",
    "[natureza orçamentária].[descrição de natureza 4 nível].[descrição de natureza 4 nível].[member_caption]": "nm_natOrcamentoNvl4",
    "[iniciativa].[iniciativas].[iniciativa].[member_caption]": "nm_iniciativa",
    "[unidade organizacional de ação].[unidade organizacional de ação].[nome de unidade organizacional de ação].[member_caption]": "nm_unidade",
    "[ação].[ação].[nome de ação].[member_caption]":"nm_acao",
    "[tempo].[ano].[número ano].[member_caption]": "vl_ano",
    "[tempo].[mês].[número mês].[member_caption]": "vl_mes",
    "[measures].[valorajustado]": "vl_ajustado",
    "cc": "nm_cc",
    "dataemissao": "nm_dataemissao",
    "categoria": "nm_categoria",
    "conta": "nm_conta",
    "complemento": "nm_complemento",
    "cdgcontanvl4": "nm_cdgOrcamentoNvl4",
    "valor": "vl_valor",
    "data": "nm_data",
    "nacional": "nm_nacional",
    "idrateio": "cdg_idrateio",
    "lctref":"cdg_referencia",
    "idpartida":"cdg_idpartida",
    "idmov": "cdg_idmov",
    "codtmv":"cdg_codtmv",
    "contrato": "cdg_contrato",
    "fornecedor": "nm_fornecedor",
    "codusuario": "nm_codusuario",
    "tipolancamento": "nm_tipolancamento",
    "acao": "nm_acao",
    "projeto": "nm_projeto",
    "unidade":"nm_unidade",
    "descnvl6": "nm_descnvl6",
    "descnvl5": "nm_descnvl5",
    "descnvl4": "nm_descnvl4",
    "descnvl3": "nm_descnvl3",
    "descnvl2": "nm_descnvl2",
    "descnvl1": "nm_descnvl1"
}

async def padroniza_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica lowercase nas colunas originais e utiliza um dicionário mapeado 
    para renomear (De -> Para). Gera auditoria das que não possuem correspondência.
    """
    colunas_iniciais: List[str] = list(df.columns)
    
    print("\n--- [TRANSFORM] Auditoria de Colunas ---")
    log.info(f"Colunas brutas identificadas: {colunas_iniciais}")
    
    colunas_renomeadas: int = 0
    colunas_sem_correspondencia: List[str] = []
    mapa_novas_colunas: Dict[str, str] = {}

    for col_original in colunas_iniciais:
        # Aplica o lower e remove espaços externos para garantir correspondência exata
        col_tratada = str(col_original).lower().strip()
        
        if col_tratada in DICIONARIO_RENOMEACAO:
            mapa_novas_colunas[col_original] = DICIONARIO_RENOMEACAO[col_tratada]
            colunas_renomeadas += 1
        else:
            # Fallback seguro: aplica formatação snake_case para colunas não mapeadas
            col_fallback = re.sub(r'\W+', '_', col_tratada).strip('_')
            mapa_novas_colunas[col_original] = col_fallback
            colunas_sem_correspondencia.append(col_tratada)
            
    # Executa a renomeação vetorizada do Pandas
    df_padronizado = df.rename(columns=mapa_novas_colunas)
    
    total_colunas: int = len(colunas_iniciais)
    total_faltantes: int = total_colunas - colunas_renomeadas

    # Relatório de execução
    print(f"Total de colunas extraídas: {total_colunas}")
    print(f"Colunas renomeadas via dicionário: {colunas_renomeadas}")
    print(f"Colunas sem correspondência (aplicado fallback snake_case): {total_faltantes}")
    
    if colunas_sem_correspondencia:
        print(f"Nomes das colunas sem correspondência: {colunas_sem_correspondencia}")
        log.warning(f"Colunas não mapeadas no dicionário: {colunas_sem_correspondencia}")
    
    print("----------------------------------------\n")
    
    return df_padronizado


async def extrai_metricas_node_js(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Prepara um payload de Data Analytics agregados, pronto para serialização JSON.
    Otimiza o consumo visual pelo backend em Node.js.
    """
    metricas: Dict[str, Any] = {
        "kpis_gerais": {
            "total_linhas": int(len(df)),
            "total_colunas": int(len(df.columns)),
        },
        "qualidade_dados": {
            "total_nulos": int(df.isnull().sum().sum())
        },
        "tipos_inferidos": {
            col: str(dtype) for col, dtype in df.dtypes.items()
        }
    }

    colunas_numericas = df.select_dtypes(include=['number']).columns.tolist()
    if colunas_numericas:
        metricas["estatisticas_numericas"] = {}
        for col in colunas_numericas:
            metricas["estatisticas_numericas"][col] = {
                "soma_total": float(df[col].sum()),
                "media": float(df[col].mean()),
                "maximo": float(df[col].max()),
                "minimo": float(df[col].min())
            }

    log.info("Métricas de Data Analytics compiladas com sucesso para consumo do Node.js.")
    return metricas


async def transforma_df(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Orquestra as etapas da camada Transform.
    
    Retorna uma tupla contendo o DataFrame transformado e o dicionário de métricas (PEP 484).
    """
    if df is None or df.empty:
        log.warning("DataFrame vazio recebido na camada de transformação. Abortando Transform.")
        return df, {}

    # 1. Padronização e Validação do Dicionário
    df_transformado = await padroniza_nomes_colunas(df)

    # 2. Geração de Métricas Analíticas
    metricas_pre_carga = await extrai_metricas_node_js(df_transformado)
    
    # Exibe métricas em tela para facilitar debug e auditoria durante o desenvolvimento
    print(f"\n[METRICAS PRE-CARGA NODE.JS] -> {metricas_pre_carga}\n")

    return df_transformado, metricas_pre_carga
