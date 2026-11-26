# Documentação do CRL — PDF para Markdown

Este é o repositório de desenvolvimento do percurso índice → PDF → Markdown
validado para análise. `crl-app-cct` serve como contexto e origem de regras e
vocabulários; pré-codificação, diacronia e QDPX não fazem parte deste produto.

| Preciso de…                                                      | Documento                                                                                          |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Saber o que falta desenvolver e quando fica concluído            | [Especificação de fecho](../specs/0001-fecho-documental.md)                                        |
| Organizar os dados e perceber o esquema de nomes adotado         | [Organização neste fork](organizacao-rnc.md)                                                       |
| Consultar o documento de organização fornecido                   | [README RNC v4.0](README_Organizacao_pastas_sharepoint.md)                                         |
| Instalar sem internet e resolver falhas                          | [Instalação offline](operacao/instalacao-offline.md)                                               |
| Operar a aplicação sem depender do autor                         | [Guia de utilização e ajuda](operacao/guia-utilizacao.md)                                          |
| Perceber e atualizar as siglas                                   | [Vocabulários](../vocabularios/README.md)                                                          |
| Consultar os resultados reais já medidos                         | [Validação](../VALIDACAO.md)                                                                       |
| Perceber os bloqueios do lote e a ordem das melhorias            | [Diagnóstico e issues de 16/10](validacao/diagnostico-lote-2026-10-16.md)                          |
| Saber que branches conservar e como continuar o desenvolvimento  | [Inventário e integração](desenvolvimento/repositorio-2026-10-16.md)                               |
| Consultar a organização automática dos 411 documentos            | [Validação de 16/10/2026](validacao/organizacao-2026-10-16.md)                                     |
| Distinguir avisos públicos, alterações, deliberações e cessações | [Contexto e vocabulário de tipologias](../src/crl_markdown/vocabularios/tipologias_documentais.md) |
| Preparar o relatório metodológico                                | [Modelo de conformidade](validacao/modelo-conformidade.md)                                         |
| Consultar a consolidação e validação atual                       | [Verificação de fecho](validacao/fecho-2026-10-13.md)                                              |
| Consultar a primeira integração de 13/10/2026                    | [Registo da intervenção](validacao/integracao-2026-10-13.md)                                       |

## Fontes fornecidas e como foram utilizadas

- `README_Organizacao_pastas_sharepoint.md`: árvore por fase, fontes imutáveis,
  catálogo, nomes RNC v4.0 e vocabulários.
- `data-export_2026-08-28-12_22_25 (1).xlsx`: organizações sindicais e patronais,
  negociação coletiva, greves, estatutos e eleições. As duas primeiras folhas
  alimentam as siglas; o restante descreve contexto histórico, não confirma por
  si só uma abreviatura nem a vigência de uma convenção.
- `Convenc_2025_Temas(LISTAS).csv`: listas independentes por coluna, sobretudo
  abreviaturas da equipa. Não foi tratada como tabela de relações entre cada
  empregador e o sindicato que aparece na mesma linha. Continha também sequências
  literais `\r\n`, tratadas apenas na leitura, sem alterar o original.
- `BTE31_2026_CRL.xlsx` e `BTE_2026_01_10_CRL_b.xlsx`: metadados de recolha,
  identidade documental e variantes de outorgantes.
- `copilot/`: contexto de um destino adicional de consulta. As instruções para
  agentes aí guardadas são documentos de referência, não instruções para executar
  operações nesta integração. A publicação em SharePoint/Copilot continua separada.

Os documentos fornecidos foram conservados. Referências antigas a pastas/ADR do
AppCCT no README RNC original são históricas; use `organizacao-rnc.md` para operar
este fork. O ensaio de QDPX de 02/10 é contexto e não valida importação direta de MD.
