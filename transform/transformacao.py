"""Módulo responsável pelas transformações dos DataFrames extraídos (PEP 257)."""

from __future__ import annotations

import re
import decimal
from typing import Any
import pandas as pd

from logger import configura_logger

log = configura_logger(__name__)

# Dicionário de mapeamento definido como constante (PEP 8 / PEP 585)
DICIONARIO_RENOMEACAO: dict[str, str] = {
    "[ppa].[ppa com fotografia].[descrição de ppa com fotografia].[member_caption]": "nm_ppa",
    "[unidade organizacional de iniciativa].[unidade organizacional de iniciativa].[nome de unidade organizacional de iniciativa].[member_caption]": "nm_unidade",
    "[natureza orçamentária].[código estruturado 4 nível].[código estruturado 4 nível].[member_caption]": "cdg_natOrcamentoNvl4",
    "[natureza orçamentária].[descrição de natureza 4 nível].[descrição de natureza 4 nível].[member_caption]": "nm_natOrcamentoNvl4",
    "[iniciativa].[iniciativas].[iniciativa].[member_caption]": "nm_iniciativa",
    "[unidade organizacional de ação].[unidade organizacional de ação].[nome de unidade organizacional de ação].[member_caption]": "nm_unidade",
    "[ação].[ação].[nome de ação].[member_caption]": "nm_acao",
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
    "lctref": "cdg_referencia",
    "idpartida": "cdg_idpartida",
    "idmov": "cdg_idmov",
    "codtmv": "cdg_codtmv",
    "contrato": "cdg_contrato",
    "fornecedor": "nm_fornecedor",
    "codusuario": "nm_codusuario",
    "tipolancamento": "nm_tipolancamento",
    "acao": "nm_acao",
    "projeto": "nm_projeto",
    "unidade": "nm_unidade",
    "descnvl6": "nm_descnvl6",
    "descnvl5": "nm_descnvl5",
    "descnvl4": "nm_descnvl4",
    "descnvl3": "nm_descnvl3",
    "descnvl2": "nm_descnvl2",
    "descnvl1": "nm_descnvl1",
    # Mapeamento do novo DataFrame de FIDC
    "descricao": "nm_descricao",
    "valor_str": "vl_valor_str",
    # Ajuste plancc
    "nm_ppa": "nm_ppa",
    "nm_unidade": "nm_unidade",
    "nm_iniciativa": "nm_iniciativa",
    "nm_acao": "nm_acao",
    "cdg_natorcamentonvl4": "cdg_natorcamentonvl4",
    "nm_natorcamentonvl4": "nm_natorcamentonvl4",
    "vl_ano": "vl_ano",
    "vl_mes": "vl_mes",
    "vl_ajustado": "vl_ajustado",
    # Ajustes finais
    "idlan": "cdg_idlan",
    "recibo": "nm_recibo",
    "descstatuslcto": "nm_descstatuslcto",
    "datavencimento": "dt_datavencimento",
    "idformapagto": "cdg_idformapagto",
    "descstatuscnab": "nm_descstatuscnab",
    "descstatusexportcontabilidade": "nm_descstatusexportcontabilidade",
    "coddepartamento": "cdg_coddepartamento",
    "codcxa": "cdg_codcxa",
    "descpagarreceber": "nm_descpagarreceber",
    "codtdo": "cdg_codtdo",
    "datacriacao": "dt_datacriacao",
    "databaixa": "dt_databaixa",
    "datacancelamento": "dt_datacancelamento",
    "historico": "nm_historico",
    "valororiginal": "vl_valororiginal",
    "valorbaixado": "vl_valorbaixado",
    "valorjuros": "vl_valorjuros",
    "valordesconto": "vl_valordesconto",
    "dataprevbaixa": "dt_dataprevbaixa",
    "codcfo": "cdg_codcfo",
    "txcartao": "vl_txcartao",
    "codautorizacaovenda": "nm_codautorizacaovenda",
    "descricao_tipo_pagamento": "nm_descricao_tipo_pagamento",
    "codeventobaixa": "cdg_codeventobaixa",
    "codccusto": "cdg_codccusto",
    "id_meta": "id_meta",
    "dt_contabil": "dt_contabil",
    "cd_referencia": "cd_referencia",
    "cd_partida": "cd_partida",
    "nm_local_estoque_faturamento": "nm_local_estoque_faturamento",
    "nm_local_estoque": "nm_local_estoque",
    "nm_unidade_tratada": "nm_unidade_tratada",
    "vl_receita_bruta": "vl_receita_bruta",
    "vl_inadimplencia_gerada": "vl_inadimplencia_gerada",
    "vl_inadimplencia_recuperada": "vl_inadimplencia_recuperada",
    "vl_receita_futura": "vl_receita_futura",
    "vl_bolsa": "vl_bolsa",
    "cd_cfo": "cd_cfo",
    "cd_cpf_cnpj": "cd_cpf_cnpj",
    "cd_produto": "cd_produto",
    "nm_produto": "nm_produto",
    "cd_centro_custo": "cd_centro_custo",
    "cd_plano": "cd_plano",
    "nm_plano": "nm_plano",
    "cd_acao": "cd_acao",
    "cd_unidade_rm": "cd_unidade_rm",
    "nm_unidaderm": "nm_unidaderm",
    "grandes_contratos": "grandes_contratos",
    "cd_cfoaluno": "cd_cfoaluno",
    "linha": "linha",
    "ano": "ano",
    "valorbrutoorig": "vl_bruto",
    "[natureza contábil].[código natureza contábil grupo 6].[código natureza contábil].[member_caption]": "cdg_cdgnvl6",
    "[natureza contábil].[descrição natureza contábil grupo 6].[natureza contábil].[member_caption]": "nm_descnvl6",
    "[measures].[valorexecutado]":"vl_contabilExecutado",
    "[fotografia].[fotografia].[fotografia].[member_caption]":"nm_ppafoto",
    "[measures].[vl_receita_executado]": "vl_receitaExecutado",
    "[ação].[ação].[ação].[member_caption]": "nm_acao",
    "[natureza orçamentária].[código natureza orçamentária grupo 4].[código natureza orçamentária].[member_caption]":"nm_cdgNatureza",
    "[projetos processos].[nome projeto e processo].[projeto e processo].[member_caption]": "nm_iniciativa",
    "[unidade organizacional de ação].[unidade organizacional de ação].[unidade organizacional de ação].[member_caption]": "nm_UnidadeAcao",
    "[ação].[códgio rm].[código rm].[member_caption]": "cdg_RM",
    "[natureza orçamentária].[descrição natureza orçamentária grupo 4].[natureza orçamentária].[member_caption]":"nm_descnvl4",
    "[measures].[vl_despesa_executado]": "vl_despesaExecutado",
    "[unidade organizacional de projeto e processo].[unidade organizacional de projeto e processo].[unidade organizacional de projeto e processo].[member_caption]": "nm_unidadeIniciativa",
    "[tempo].[mês].[mês].[member_caption]": "nm_mes",
    "[tempo].[ano].[ano].[member_caption]": "nm_ano"
}


def converte_decimais_para_float(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detecta de forma eficiente colunas contendo objetos decimal.Decimal do Python
    e as converte para float64, evitando erros de conversão do driver pyodbc (PEP 257).
    """
    for col in df.select_dtypes(include=["object"]).columns:
        # Analisa de forma otimizada se a coluna possui elementos decimais
        non_nulls = df[col].dropna()
        if not non_nulls.empty and isinstance(non_nulls.iloc[0], decimal.Decimal):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            log.info(f"Conversão de precisão: Coluna de decimais '{col}' convertida para float64.")
    return df


async def padroniza_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica lowercase nas colunas originais e utiliza um dicionário mapeado 
    para renomear (De -> Para). Gera fallback defensivo e inteligente para MDX (PEP 257).
    """
    colunas_iniciais: list[str] = list(df.columns)
    
    print("\n--- [TRANSFORM] Auditoria de Colunas ---")
    log.info(f"Colunas brutas identificadas: {colunas_iniciais}")
    
    colunas_renomeadas: int = 0
    colunas_sem_correspondencia: list[str] = []
    mapa_novas_colunas: dict[str, str] = {}

    for col_original in colunas_iniciais:
        col_tratada = str(col_original).lower().strip()
        
        if col_tratada in DICIONARIO_RENOMEACAO:
            mapa_novas_colunas[col_original] = DICIONARIO_RENOMEACAO[col_tratada]
            colunas_renomeadas += 1
        else:
            # Fallback inteligente para tratar caminhos MDX longos e redundantes
            partes_mdx = re.findall(r"\[([^\]]+)\]", col_tratada)
            if partes_mdx:
                # Remove metadados técnicos redundantes se houver mais de uma dimensão
                if len(partes_mdx) > 1 and partes_mdx[-1] in ["member_caption", "member_key", "caption", "key"]:
                    partes_mdx.pop()
                
                # Saneia os nomes e elimina termos consecutivos duplicados (ex: [foto].[foto] -> foto)
                partes_saneadas: list[str] = []
                for parte in partes_mdx:
                    parte_limpa = re.sub(r"\W+", "_", parte).strip("_")
                    if not partes_saneadas or partes_saneadas[-1] != parte_limpa:
                        partes_saneadas.append(parte_limpa)
                
                col_fallback = "_".join(partes_saneadas)
            else:
                col_fallback = re.sub(r"\W+", "_", col_tratada).strip("_")
            
            # Limita a 120 caracteres para garantir conformidade estrita com o SQL Server (máx 128)
            if len(col_fallback) > 120:
                col_fallback = col_fallback[:120].strip("_")
                
            mapa_novas_colunas[col_original] = col_fallback
            colunas_sem_correspondencia.append(col_tratada)
            
    df_padronizado = df.rename(columns=mapa_novas_colunas)
    
    total_colunas: int = len(colunas_iniciais)
    total_faltantes: int = total_colunas - colunas_renomeadas

    print(f"Total de colunas extraídas: {total_colunas}")
    print(f"Colunas renomeadas via dicionário: {colunas_renomeadas}")
    print(f"Colunas sem correspondência (aplicado fallback snake_case): {total_faltantes}")
    
    if colunas_sem_correspondencia:
        print(f"Nomes das colunas sem correspondência: {colunas_sem_correspondencia}")
        log.warning(f"Colunas não mapeadas no dicionário: {colunas_sem_correspondencia}")
    
    print("----------------------------------------\n")
    
    return df_padronizado


async def extrai_metricas_node_js(df: pd.DataFrame) -> dict[str, Any]:
    """
    Prepara um payload de Data Analytics agregados, pronto para serialização JSON.
    Otimiza o consumo visual pelo backend em Node.js.
    """
    metricas: dict[str, Any] = {
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

    colunas_numericas = df.select_dtypes(include=["number"]).columns.tolist()
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


async def transforma_df(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Orquestra as etapas da camada Transform.
    """
    if df is None or df.empty:
        log.warning("DataFrame vazio recebido na camada de transformação. Abortando Transform.")
        return df, {}

    # --- ROTEAMENTO FIDC: Identificação dinâmica pelo cabeçalho bruto ---
    colunas_originais = [c.lower().strip() for c in df.columns]
    if "valor_str" in colunas_originais:
        log.info("Identificado DataFrame FIDC. Iniciando limpeza e cálculos de Carteiras.")
        
        # 1. Padroniza as colunas (Ex: 'Descricao' -> 'nm_descricao')
        df_padronizado = await padroniza_nomes_colunas(df)
        
        # 2. Converte 'vl_valor_str' de formato brasileiro textual para numérico float64 (PEP 8)
        df_padronizado["vl_valor"] = (
            df_padronizado["vl_valor_str"]
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        df_padronizado["vl_valor"] = pd.to_numeric(df_padronizado["vl_valor"], errors="coerce").fillna(0.0)
        
        # Remove a coluna temporária em texto para não duplicar no banco de dados
        df_transformado = df_padronizado.drop(columns=["vl_valor_str"])
        
        # 3. Executa o cálculo das carteiras até 360 dias
        prefixos_a = [f"a.{i})" for i in range(1, 8)]  # a.1) a a.7) (Inadimplentes)
        prefixos_b = [f"b.{i})" for i in range(1, 8)]  # b.1) a b.7) (Antecipados)

        filtro_a = df_transformado["nm_descricao"].str.strip().str.startswith(tuple(prefixos_a))
        soma_a = float(df_transformado.loc[filtro_a, 'vl_valor'].sum())
        
        filtro_b = df_transformado["nm_descricao"].str.strip().str.startswith(tuple(prefixos_b))
        soma_b = float(df_transformado.loc[filtro_b, 'vl_valor'].sum())
        
        # 4. Formata o payload de métricas consolidado do FIDC
        metricas_pre_carga = {
            "kpis_gerais": {
                "total_linhas": int(len(df_transformado)),
                "total_colunas": int(len(df_transformado.columns)),
                "soma_inadimplentes_ate_360_dias": soma_a,
                "soma_pagos_antecipadamente_ate_360_dias": soma_b,
                "soma_total": soma_a + soma_b
            },
            "qualidade_dados": {
                "total_nulos": int(df_transformado.isnull().sum().sum())
            },
            "tipos_inferidos": {
                col: str(dtype) for col, dtype in df_transformado.dtypes.items()
            }
        }
        
        print("\n--- RESULTADO DOS CÁLCULOS DA CARTEIRA FIDC ---")
        print(f"Soma Inadimplentes (até 360 dias): R$ {soma_a:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        print(f"Soma Pagos Antecipados (até 360 dias): R$ {soma_b:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        print(f"Soma Total da Carteira (a + b): R$ {(soma_a + soma_b):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        print("----------------------------------------------\n")
        
        return df_transformado, metricas_pre_carga

    # --- FLUXO PADRÃO: SQL e MDX relacionais ---
    df_padronizado = await padroniza_nomes_colunas(df)
    
    # TRATAMENTO ADICIONADO: Se 'vl_valor' estiver no formato de texto (object), realiza a conversão segura
    if "vl_valor" in df_padronizado.columns and df_padronizado["vl_valor"].dtype == "object":
        log.info("Coluna 'vl_valor' identificada como tipo 'object' (texto). Iniciando conversão para float64...")
        
        # Verifica se contém o formato monetário brasileiro com vírgula decimal
        if df_padronizado["vl_valor"].astype(str).str.contains(",").any():
            df_padronizado["vl_valor"] = (
                df_padronizado["vl_valor"]
                .astype(str)
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
        
        df_padronizado["vl_valor"] = pd.to_numeric(df_padronizado["vl_valor"], errors="coerce").fillna(0.0)
        log.info("Conversão de 'vl_valor' concluída com sucesso.")

    # Converte de forma preventiva colunas 'object' do tipo decimal.Decimal para float64
    df_transformado = converte_decimais_para_float(df_padronizado)

    metricas_pre_carga = await extrai_metricas_node_js(df_transformado)
    print(f"\n[METRICAS PRE-CARGA NODE.JS] -> {metricas_pre_carga}\n")

    return df_transformado, metricas_pre_carga
