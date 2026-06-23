"""Módulo responsável pela interface interativa (UI) do pipeline DEX no terminal com suporte a Combos (PEP 257)."""

import os
from typing import List, Tuple, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from extract.config.config import SetaDF

console = Console()

# Definição das Playlists (Combos de execução rápida)
PLAYLISTS: Dict[str, Dict[str, Any]] = {
    "P1": {
        "nome": "PPR Custos (Orçamento & Planejamento)",
        "desc": "Atualiza as bases de orçamento, planejamento e despesas (PPR Custos)",
        "bases": ["orcado", "plancc", "smedespesas"]
    },
    "P2": {
        "nome": "Grupo DW Leme (Contábil & Execução)",
        "desc": "Atualiza as bases contábeis e de execução financeira",
        "bases": ["lemecontabil", "lemedespexec", "lemerecexec"]
    },
    "P3": {
        "nome": "Receitas & Inadimplência",
        "desc": "Gera informações de faturamento, metas de receita e inadimplência",
        "bases": ["orcado_receitas", "orcado_receitas_cenario", "metareceita", "inadim"]
    },
    "P4": {
        "nome": "Fechamento & FIDC",
        "desc": "Fatos de fechamento de caixa e dados estruturados da carteira FIDC",
        "bases": ["fatofechamento", "fatoajustadonacional", "fidc"]
    }
}


def exibir_menu_seletor(entidades_disponiveis: List[SetaDF]) -> Tuple[List[str], bool]:
    """
    Exibe uma interface de terminal (UI) moderna com suporte a seleção de 
    playlists de execução e seleção individual de processos.

    :param entidades_disponiveis: Lista de entidades (SetaDF) carregadas do projeto.
    :return: Uma tupla contendo (Lista de nomes das entidades selecionadas, Flag de executar carga).
    """
    if not entidades_disponiveis:
        console.print("[bold red]Nenhum processo ou query foi localizado no projeto![/bold red]")
        return [], True

    # Normaliza e ordena o nome dos processos carregados fisicamente no projeto
    nomes_processos = [e.origem.nome_processo.lower().strip() for e in entidades_disponiveis]
    nomes_processos.sort()

    while True:
        console.clear()
        
        # 1. Cabeçalho Geral
        console.print(Panel(
            "[bold green]DEX - Painel Interativo de Orquestração (ETL)[/bold green]\n"
            "[dim]Selecione uma Playlist (Combo) ou selecione tabelas individuais para rodar o pipeline.[/dim]",
            border_style="green",
            title="Sebraesp DEX UI",
            title_align="left"
        ))

        # 2. Painel de Playlists (Combos Predefinidos)
        tabela_playlists = Table(show_header=True, header_style="bold yellow", border_style="dim", expand=True)
        tabela_playlists.add_column("Código", justify="center", style="bold cyan", width=10)
        tabela_playlists.add_column("Nome do Combo (Playlist)", style="white", width=35)
        tabela_playlists.add_column("Descrição do Fluxo", style="dim")
        tabela_playlists.add_column("Bases Incluídas", style="magenta")

        for codigo, info in PLAYLISTS.items():
            bases_com_recuo = ", ".join(info["bases"])
            tabela_playlists.add_row(codigo, info["nome"], info["desc"], bases_com_recuo)

        console.print(Panel(tabela_playlists, title="[bold yellow]Playlists / Combos Rápidos[/bold yellow]", border_style="yellow"))

        # 3. Painel de Consultas Individuais
        tabela_individuais = Table(show_header=True, header_style="bold magenta", border_style="dim", expand=True)
        tabela_individuais.add_column("ID", justify="center", style="cyan", width=10)
        tabela_individuais.add_column("Nome da Consulta Individual", style="white")
        tabela_individuais.add_column("Tipo de Banco / Conexão", style="yellow", justify="center")

        mapa_auxiliar = {}
        for idx, nome in enumerate(nomes_processos, start=1):
            entidade = next(e for e in entidades_disponiveis if e.origem.nome_processo.lower().strip() == nome)
            tabela_individuais.add_row(str(idx), nome, entidade.origem.tipo.upper())
            mapa_auxiliar[idx] = nome

        console.print(Panel(tabela_individuais, title="[bold magenta]Consultas Disponíveis para Seleção Individual[/bold magenta]", border_style="magenta"))

        # 4. Instruções de Operação
        console.print("\n[bold white]Instruções de Uso:[/bold white]")
        console.print("• Digite o Código do Combo (Ex: [bold cyan]P1[/bold cyan]) para rodar a playlist de uma vez.")
        console.print("• Digite os IDs individuais separados por vírgula (Ex: [bold cyan]1,3,5[/bold cyan]).")
        console.print("• Digite [bold cyan]A[/bold cyan] para rodar [bold]TODAS[/bold] as consultas.")
        console.print("• Digite [bold red]Q[/bold red] para cancelar e sair.\n")

        opcao = Prompt.ask("[bold white]Escolha uma opção (ID, Playlist ou Comando)[/bold white]").strip().upper()

        if opcao == 'Q':
            console.print("[bold red]Operação cancelada pelo usuário. Saindo...[/bold red]")
            return [], True
        
        selecionados: List[str] = []

        # Opção 1: Seleção de Playlist Completa
        if opcao in PLAYLISTS:
            combo = PLAYLISTS[opcao]
            # Valida se de fato os nomes das bases existem no projeto
            selecionados = [b for b in combo["bases"] if b in nomes_processos]
            console.print(f"\n[bold green]Combo ativado:[/bold green] {combo['nome']}")
        
        # Opção 2: Rodar tudo
        elif opcao == 'A':
            selecionados = nomes_processos
            console.print(f"\n[bold green]Você optou por rodar todas as bases cadastradas.[/bold green]")
            
        # Opção 3: Seleção manual separada por vírgulas
        else:
            partes = opcao.split(",")
            for parte in partes:
                parte_limpa = parte.strip()
                if parte_limpa.isdigit():
                    num = int(parte_limpa)
                    if num in mapa_auxiliar:
                        selecionados.append(mapa_auxiliar[num])
            
            if not selecionados:
                Prompt.ask("\n[bold red]⚠️ Escolha inválida! Pressione Enter para tentar novamente.[/bold red]")
                continue

        # Exibe o sumário das tabelas prontas para execução
        console.print(f"[bold yellow]Tabelas prontas para executar:[/bold yellow] [green]{', '.join(selecionados)}[/green]\n")
        
        # Pergunta se o usuário deseja efetuar a carga no banco
        executar_carga = Confirm.ask(
            "[bold white]Deseja realizar a persistência/carga final no Banco de Dados (dbo.dex-*)? [/bold white]",
            default=True
        )

        return selecionados, executar_carga
