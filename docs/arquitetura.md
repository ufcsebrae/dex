# Arquitetura de Dados - DEX (Data Extraction & X-port)

Este documento descreve a topologia, os fluxos e a organização do pipeline de dados DEX para auditoria e inteligência orçamentária do Sebrae-SP.

## 1. Visão Geral do Pipeline

```text
[Bancos / OLAP] ──(extracao)──> [Memória (SetaDF)] ──(transformacao)──> [Métricas + Dados Limpos] ──(carga)──> [SQL Server (FINANCA)]
