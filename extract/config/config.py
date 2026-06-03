"""Módulo de modelos de dados utilizando conceitos de Composição e DDD (PEP 257)."""
from typing import Any
from pydantic import BaseModel, Field, ConfigDict

class OrigemConfig(BaseModel):
    """
    Value Object (Infraestrutura): Armazena estritamente os dados de conexão.
    Não possui identidade, apenas define os parâmetros de acesso.
    """
    nome_processo: str = Field(
        ...,
        title='Título do processo',
        description='Identificador da conexão originado no .env'
    )
    tipo: str = Field(..., description='Tipo do banco de dados (ex: sql, olap, azure_sql)')
    database: str | None = Field(default=None, description='Nome do banco de dados')
    servidor: str | None = Field(default=None, description='Endereço do servidor')
    driver: str | None = Field(default=None, description='Driver utilizado para a conexão')
    string_connection: str = Field(..., description='String de conexão montada pronta para uso')

class SetaDF(BaseModel):
    """
    Entity (Domínio): Representa o produto de dados extraído.
    Agrupa a regra (query), o resultado (df) e a linhagem (origem).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    origem: OrigemConfig = Field(..., description='Value Object com as configurações da conexão original')
    query: str = Field(..., description='Query SQL ou MDX que gerou este produto de dados')
    df: Any | None = Field(default=None, description='DataFrame contendo os dados extraídos')
