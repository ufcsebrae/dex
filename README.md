# DEX — Data Extraction & X-port

O **DEX** é um orquestrador de dados concorrente, modular e declarativo de nível corporativo desenvolvido em Python para o Sebrae-SP. Ele centraliza, higieniza, calcula e consolida informações provenientes de múltiplas origens (SQL Server Relacional, Azure Synapse, Cubos OLAP e Web Scraping do site FNET B3) carregando-as de forma fracionada no banco de dados `FINANCA`.

---

## 1. Topologia de Pastas e Componentes do Sistema

O projeto segue conceitos de **DDD (Domain-Driven Design)**, separando de forma clara as responsabilidades de Domínio, Infraestrutura e Interface (Orquestração).

| Caminho do Diretório | Tipo de Componente | Descrição Funcional |
|:---|:---|:---|
| `main.py` | Orquestrador (Interface) | Controla o fluxo de execução, argumentos CLI e interface do console. |
| `logger.py` | Core (Suporte) | Módulo de logs estruturados em conformidade com a PEP 282 e otimizado para I/O. |
| `requirements.txt` | Configuração | Relação completa de dependências físicas do ambiente virtual. |
| `extract/` | Infraestrutura | Módulo de extração de dados multifonte (Bancos e Scraping). |
| `extract/queries/` | Recursos | Pasta de armazenamento de scripts analíticos (.sql, .mdx e .json de parâmetros). |
| `extract/mapa_queries.json` | Configuração | Mapeamento declarativo entre arquivos de queries e chaves de conexões. |
| `transform/` | Domínio | Camada de higienização de strings (snake_case) e cálculos de KPIs do FIDC. |
| `load/` | Infraestrutura | Motor de carga fragmentada (chunks) e gravação de logs de auditoria. |
| `estudos/` | Análise | Centralização de notebooks e estudos interativos de dados (#%%). |
| `docs/` | Documentação | Pasta dedicada para documentação e diagramas de arquitetura. |

---

## 2. Roteamento de Origens e Conexões

O DEX integra as fontes de dados do Sebrae-SP por meio de um dicionário JSON no arquivo de ambiente `.env`, mapeando as engines conforme a tabela abaixo:

| ID da Conexão | Tipo de Engine | Origem Física | Driver Utilizado |
|:---|:---|:---|:---|
| `SPSVSQL39_HubDados` | SQL Server | Banco Relacional local (SPSVSQL39) | ODBC Driver 18 for SQL Server |
| `OLAP_SME` | SSAS Cubo | Servidor OLAP corporativo (SME) | Microsoft.AnalysisServices.AdomdClient |
| `AZURE` | Synapse SQL | Banco de Dados na nuvem do Azure | ODBC Driver 18 for SQL Server |
| `FIDC` | Web Driver | Plataforma FNET da B3 (Web Scraping) | Python `requests` & `BeautifulSoup` |

---

## 3. Inteligência de Precedência de Carga (Dependências)

O orquestrador resolve dependências topológicas automaticamente por meio do dicionário `MAPA_DEPENDENCIAS` no `main.py`. Se você executar uma query que depende de outra tabela física no banco, o sistema gerenciará a ordem de execução conforme abaixo:

| Query de Destino | Dependência Obrigatória | Comportamento do Orquestrador |
|:---|:---|:---|
| `metareceita` | `orcado` | Executa e sobe o `orcado` primeiro. |
| `plancc` | `orcado` | Executa e sobe o `orcado` primeiro. |
| `plancc` | `fatoajustadonacional` | Executa e sobe a `fatoajustadonacional` primeiro. |

---

## 4. Diferenciais Técnicos e Blindagens de Rede

O sistema adota padrões defensivos robustos de engenharia de software para garantir a integridade das cargas:

| Recurso Técnico | Solução Adotada | Benefício de Engenharia |
|:---|:---|:---|
| **Carga Fracionada** | Divisão de dados em *chunks* dinâmicos de tamanho otimizado. | Evita estouro de memória (buffer overflow) no SQL Server. |
| **fast_executemany** | Habilitado nativamente no conector SQLAlchemy do SQLAlchemy. | Acelera em até 30x a velocidade de gravação por rede corporativa. |
| **Anti-Gargalo de Handshake** | Injeção automática de `Encrypt=no;` no driver do SQL Server. | Resolve falhas de handshake TLS/SSL locais (Erro 10054). |
| **Blindagem T-SQL** | Varredura com `cursor.nextset()` e desativação com `SET NOCOUNT ON;` | Executa scripts SQL complexos com tabelas temporárias com sucesso. |
| **Cache de Estudos** | Banco local SQLite (`data/cache.db`) com política Read-Through. | Pula consultas de rede pesadas em sessões interativas de análise. |

---

## 5. Interface de Linha de Comando (Como Executar)

O orquestrador aceita comandos flexíveis para desenvolvimento e produção:

| Comando de Execução | Fases Executadas | Objetivo Principal |
|:---|:---|:---|
| `python main.py` | 1, 2, 3 e 4 | Executa o pipeline de ponta a ponta para todas as queries cadastradas. |
| `python main.py plancc` | 1, 2, 3 e 4 | Executa o pipeline completo exclusivamente para o plano de centros de custo. |
| `python main.py plancc --sem-carga` | 1 e 2 apenas | Roda extração e higienização, mas pula a gravação no SQL Server (Dry Run). |
| `python main.py --ignorar-dependencias` | Variável | Pula o prompt interativo do console e executa todas as tabelas diretamente. |

---

## 6. Como Adicionar Novas Tabelas ao DEX

O DEX foi projetado para ser estendido de forma 100% declarativa, sem necessidade de alteração de código Python para novos relatórios:

1. **Para Queries SQL/MDX**: Salve o seu arquivo de instrução (ex: `meu_relatorio.sql` ou `meu_relatorio.mdx`) na pasta `extract/queries/`.
2. **Para Parâmetros de Web Scraping**: Salve o seu arquivo de parâmetros em formato JSON (ex: `meu_fundo.json`) na pasta `extract/queries/`.
3. **Atualize o Mapeamento**: No arquivo `extract/mapa_queries.json`, registre a chave criada associando-a à sua respectiva conexão de origem do `.env` (ex: `"meu_relatorio": "AZURE"`).
"""

with open("README.md", "w", encoding="utf-8") as f:
    f.write(readme_content)

print("README.md successfully written to current directory.")

