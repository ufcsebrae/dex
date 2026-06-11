"""Módulo de orquestração do pipeline de ETL com inteligência de precedência interativa (PEP 257)."""

import asyncio
import argparse
from typing import Callable, Dict, List, Optional
import nest_asyncio
import pandas as pd
from dotenv import load_dotenv

# Carrega as variáveis de ambiente antes de qualquer importação de submódulos (PEP 20)
load_dotenv()

# Importações do Rich para múltiplas barras de progresso
from rich.progress import (
    Progress, 
    SpinnerColumn, 
    TextColumn, 
    BarColumn, 
    TaskProgressColumn, 
    TimeElapsedColumn
)

from logger import configura_logger
from extract.extracao import buscar_dados, extrair_dataframe_da_origem
from transform.transformacao import transforma_df
from load.carga import salva_df, salva_metricas, ler_tabela_carregada
from extract.config.config import SetaDF 

nest_asyncio.apply()
log = configura_logger(__name__)

MAPA_DEPENDENCIAS: Dict[str, List[str]] = {
    # "metareceita": ["orcado"],
    "plancc": ["orcado"]  # 'plancc' garantirá que o orçado E a fato nacional estejam atualizados!
}


class RichProgressObserver:
    """
    Classe responsável por gerenciar a UI do Rich (PEP 20).
    Desacopla estritamente a interface visual da regra de negócio do ETL.
    """
    def __init__(self, progress: Progress) -> None:
        self.progress: Progress = progress
        self.tasks: Dict[str, int] = {}

    def adicionar_tarefa(self, nome_processo: str, total_etapas: int) -> None:
        """Registra uma nova tarefa visual no painel do Rich."""
        task_id: int = self.progress.add_task(
            f"[dim]Aguardando: {nome_processo}", 
            total=total_etapas
        )
        self.tasks[nome_processo] = task_id

    def notificar(self, nome_processo: str, description: str, avanco: int = 0) -> None:
        """Callback injetado nas rotinas para atualizar as barras de progresso."""
        task_id: Optional[int] = self.tasks.get(nome_processo)
        if task_id is not None:
            self.progress.update(task_id, description=description)
            if avanco > 0:
                self.progress.advance(task_id, advance=avanco)


def perguntar_atualizacao_dependencias(deps: List[str]) -> bool:
    """
    Pergunta de forma interativa no console se o usuário deseja 
    atualizar as dependências detectadas (PEP 20).
    """
    print(f"\n[ATENÇÃO] O pipeline identificou dependências obrigatórias: {deps}")
    while True:
        resposta = input("Deseja executar e atualizar estas dependências antes de prosseguir? [S/n]: ").strip().lower()
        if resposta in ["", "s", "sim", "y", "yes"]:
            return True
        elif resposta in ["n", "nao", "não", "no"]:
            return False
        else:
            print("Resposta inválida. Digite 'S' para Sim ou 'N' para Não.")


async def processar_entidade(
    entidade: SetaDF, 
    callback_notificacao: Callable[[str, str, int], None],
    executar_carga: bool = True
) -> None:
    """
    Executa o pipeline de dados de forma assíncrona. 
    Permite omitir as etapas de carga do banco.
    """
    nome_processo: str = entidade.origem.nome_processo
    etapas_concluidas: int = 0
    total_etapas: int = 4 if executar_carga else 2
    
    try:
        # 1. Extração
        callback_notificacao(nome_processo, f"[cyan]Extraindo: {nome_processo}", 0)
        entidade_processada = await extrair_dataframe_da_origem(entidade)
        etapas_concluidas += 1
        callback_notificacao(nome_processo, f"[cyan]Extração concluída: {nome_processo}", 1)
        
        if entidade_processada.df is None or entidade_processada.df.empty:
            log.warning(f"Sem dados para '{nome_processo}'.")
            callback_notificacao(
                nome_processo, 
                f"[yellow]Sem dados: {nome_processo}", 
                total_etapas - etapas_concluidas
            )
            return

        # 2. Transformação (Retorna o DataFrame transformado e o dicionário de métricas)
        callback_notificacao(nome_processo, f"[magenta]Transformando: {nome_processo}", 0)
        df_transformado, metricas = await transforma_df(entidade_processada.df)
        etapas_concluidas += 1
        
        if not executar_carga:
            callback_notificacao(nome_processo, f"[bold green]Transformado: {nome_processo}", 1)
            log.info(f"Pipeline '{nome_processo}' concluído após transformação (modo sem carga).")
            return
            
        callback_notificacao(nome_processo, f"[magenta]Transformação concluída: {nome_processo}", 1)

        # 3. Carga do DataFrame Transformado (Load 1)
        def reportar_progresso_carga(porcentagem: int) -> None:
            callback_notificacao(
                nome_processo, 
                f"[yellow]Gravando Dados: {nome_processo} ({porcentagem}%)", 
                0
            )

        callback_notificacao(nome_processo, f"[yellow]Gravando Dados: {nome_processo} (0%)", 0)
        await salva_df(df_transformado, nome_processo, on_progress=reportar_progresso_carga)
        etapas_concluidas += 1
        callback_notificacao(nome_processo, f"[yellow]Carga de Dados concluída: {nome_processo}", 1)

        # 4. Carga das Métricas de Auditoria (Load 2)
        callback_notificacao(nome_processo, f"[blue]Carregando Métricas: {nome_processo}", 0)
        await salva_metricas(metricas, nome_processo)
        etapas_concluidas += 1
        callback_notificacao(nome_processo, f"[bold green]Concluído com Sucesso: {nome_processo}", 1)
        
    except Exception as erro_processo:
        log.error(f"Falha no pipeline '{nome_processo}': {erro_processo}")
        passos_restantes: int = total_etapas - etapas_concluidas
        callback_notificacao(
            nome_processo, 
            f"[bold red]Erro: {nome_processo}", 
            passos_restantes
        )


async def obter_dados_em_memoria(entidades_alvo: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
    """
    Executa apenas as fases de Extração e Transformação de forma concorrente,
    retornando um dicionário de DataFrames prontos para análise (Jupyter / #%%).
    """
    lista_entidades = await buscar_dados()
    if not lista_entidades:
        log.error("Nenhuma configuração encontrada.")
        return {}

    if entidades_alvo:
        mapa_alvos = [a.lower() for a in entidades_alvo]
        lista_entidades = [e for e in lista_entidades if e.origem.nome_processo.lower() in mapa_alvos]

    dicionario_dataframes: Dict[str, pd.DataFrame] = {}

    async def _processa_paralelo(entidade: SetaDF) -> None:
        nome = entidade.origem.nome_processo
        try:
            entidade_proc = await extrair_dataframe_da_origem(entidade)
            if entidade_proc.df is not None and not entidade_proc.df.empty:
                df_trans, _ = await transforma_df(entidade_proc.df)
                dicionario_dataframes[nome] = df_trans
                log.info(f"Tabela '{nome}' carregada em memória com sucesso.")
        except Exception as err:
            log.error(f"Erro ao carregar '{nome}' para memória: {err}")

    await asyncio.gather(*[_processa_paralelo(e) for e in lista_entidades])
    return dicionario_dataframes


async def obter_dados_carregados_em_memoria(entidades_alvo: Optional[List[str]] = None) -> Dict[str, pd.DataFrame]:
    """
    Busca as tabelas correspondentes diretamente do banco de dados FINANCA (dbo.dex-*),
    sem precisar reexecutar a extração dos cubos OLAP ou de arquivos brutos.
    """
    lista_entidades = await buscar_dados()
    if not lista_entidades:
        log.error("Nenhuma configuração encontrada.")
        return {}

    if entidades_alvo:
        mapa_alvos = [a.lower() for a in entidades_alvo]
        lista_entidades = [e for e in lista_entidades if e.origem.nome_processo.lower() in mapa_alvos]

    dicionario_dataframes: Dict[str, pd.DataFrame] = {}
    loop = asyncio.get_running_loop()

    async def _busca_paralelo(nome_processo: str) -> None:
        try:
            df = await loop.run_in_executor(None, ler_tabela_carregada, nome_processo)
            if df is not None and not df.empty:
                dicionario_dataframes[nome_processo] = df
                log.info(f"Tabela de Carga '{nome_processo}' lida do SQL Server com sucesso.")
        except Exception as err:
            log.error(f"Erro ao ver tabela carregada '{nome_processo}': {err}")

    await asyncio.gather(*[_busca_paralelo(e.origem.nome_processo) for e in lista_entidades])
    return dicionario_dataframes


async def executa_pipeline_concorrente(
    entidades_alvo: Optional[List[str]] = None,
    executar_carga: bool = True,
    ignorar_dependencias: bool = False
) -> None:
    """Orquestra o pipeline resolvendo dependências de precedência de forma sequencial ou paralela interativa."""
    lista_entidades_total: List[SetaDF] = await buscar_dados()
    
    if not lista_entidades_total:
        log.error("Nenhuma configuração encontrada.")
        return

    # 1. Filtra as entidades alvo que o usuário escolheu processar
    entidades_a_processar: List[SetaDF] = []
    if entidades_alvo:
        mapa_entidades = {e.origem.nome_processo.lower(): e for e in lista_entidades_total}
        for alvo in entidades_alvo:
            chave_alvo = alvo.lower()
            if chave_alvo in mapa_entidades:
                entidades_a_processar.append(mapa_entidades[chave_alvo])
            else:
                log.warning(f"Entidade '{alvo}' ignorada (não encontrada na base de queries).")
    else:
        entidades_a_processar = lista_entidades_total

    if not entidades_a_processar:
        return

    # 2. Resolução de Dependências Automática
    pre_requisitos_a_processar: List[SetaDF] = []
    
    if not ignorar_dependencias:
        for entidade in entidades_a_processar:
            nome_l = entidade.origem.nome_processo.lower()
            if nome_l in MAPA_DEPENDENCIAS:
                deps_necessarias = MAPA_DEPENDENCIAS[nome_l]
                for dep in deps_necessarias:
                    dep_lower = dep.lower()
                    entidade_dep = next((e for e in lista_entidades_total if e.origem.nome_processo.lower() == dep_lower), None)
                    if entidade_dep and entidade_dep not in pre_requisitos_a_processar:
                        pre_requisitos_a_processar.append(entidade_dep)

        # Se houver pré-requisitos, faz a pergunta interativa
        if pre_requisitos_a_processar:
            nomes_deps = [p.origem.nome_processo for p in pre_requisitos_a_processar]
            deseja_atualizar = perguntar_atualizacao_dependencias(nomes_deps)
            
            # Se o usuário escolher não processar antes, limpa a lista de precedência
            if not deseja_atualizar:
                pre_requisitos_a_processar = []
                log.info("Sinalizado pelo usuário: Pré-requisitos serão executados em paralelo com a carga normal.")

    # Filtra as entidades principais (remove os pré-requisitos que rodarão na primeira onda)
    entidades_principais = [
        e for e in entidades_a_processar 
        if e.origem.nome_processo.lower() not in [p.origem.nome_processo.lower() for p in pre_requisitos_a_processar]
    ]

    total_etapas: int = 4 if executar_carga else 2

    # ONDA 1: Executa e sobe os pré-requisitos antes de todos
    if pre_requisitos_a_processar:
        log.info(f"Processando dependências prioritárias em primeiro plano: {[p.origem.nome_processo for p in pre_requisitos_a_processar]}...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
        ) as progress:
            observador = RichProgressObserver(progress)
            tasks_async = []
            for entidade in pre_requisitos_a_processar:
                nome = entidade.origem.nome_processo
                observador.adicionar_tarefa(nome_processo=nome, total_etapas=total_etapas)
                corrotina = processar_entidade(entidade, observador.notificar, executar_carga)
                tasks_async.append(corrotina)
                
            await asyncio.gather(*tasks_async)
            
        log.info("Pré-requisitos atualizados. Prosseguindo para o processamento das tabelas principais...")

    # ONDA 2: Executa os pipelines concorrentes restantes em paralelo
    if entidades_principais:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
        ) as progress:
            observador = RichProgressObserver(progress)
            tasks_async = []
            for entidade in entidades_principais:
                nome = entidade.origem.nome_processo
                observador.adicionar_tarefa(nome_processo=nome, total_etapas=total_etapas)
                corrotina = processar_entidade(entidade, observador.notificar, executar_carga)
                tasks_async.append(corrotina)
                
            await asyncio.gather(*tasks_async)

    log.info("Todos os processos finalizados com sucesso.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Orquestrador do Pipeline de ETL.")
    parser.add_argument(
        'entidades', 
        nargs='*', 
        help="Nomes das bases específicas que deseja rodar. Ex: orcado fatofechamento"
    )
    parser.add_argument(
        '--sem-carga', 
        action='store_true', 
        help="Executa apenas a Extração (1) e a Transformação (2), ignorando a etapa de Carga no banco."
    )
    parser.add_argument(
        '--ignorar-dependencias',
        action='store_true',
        help="Pula o prompt interativo e executa todas as tabelas diretamente em paralelo."
    )
    args = parser.parse_args()
    
    executar_carga: bool = not args.sem_carga
    
    asyncio.run(
        executa_pipeline_concorrente(
            entidades_alvo=args.entidades or None, 
            executar_carga=executar_carga,
            ignorar_dependencias=args.ignorar_dependencias
        )
    )

if __name__ == "__main__":
    main()
