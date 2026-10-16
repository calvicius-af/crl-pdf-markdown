# Avisos públicos e cessações — correção de 16/10/2026

Esta intervenção substitui a classificação dos 11 avisos como «apenas metadados».
Foram organizados os **411 PDFs** do lote, com zero pendentes de nomeação.

## Recursos instalados

- [Contexto documental](../../src/crl_markdown/vocabularios/tipologias_documentais.md):
  critérios, fonte da decisão funcional, precedência, identidade, relações e auditoria.
- [Vocabulário executável](../../src/crl_markdown/vocabularios/tipologias_documentais.json):
  regras versionadas de classificação. O tipo publicado continua no campo `tipo`;
  a natureza reconhecida fica em `tipo_documental`.
- `0_gestao/catalogo/relacoes_documentais.json`: relações por publicação e processo.
  A coluna `relacoes_documentais` do catálogo anual conserva a mesma informação em JSON.

O contexto Markdown e o vocabulário JSON são incluídos na wheel e copiados para
`0_gestao/vocabularios` ao inicializar a pasta RNC. Edições existentes da equipa
são conservadas. A organização local consulta a versão do vocabulário dessa pasta.

## Reclassificação aplicada

| Publicação                                 | Natureza                    | Referência da base                           | Destino            |
| ------------------------------------------ | --------------------------- | -------------------------------------------- | ------------------ |
| Aviso 1/2026, Figueiró dos Vinhos–SINTAP   | ACEP-ALT, texto consolidado | 53/2016                                      | convencoes/APU     |
| Aviso 2/2026, Alpiarça–STFPSSRA            | ACEP-ALT                    | 322/2015                                     | convencoes/APU     |
| Aviso 3/2026, Alvaiázere–SINTAP            | ACEP-ALT, texto consolidado | 74/2015                                      | convencoes/APU     |
| Aviso 4/2026, Óbidos–SINTAP                | ACEP-ALT, texto consolidado | 66/2015                                      | convencoes/APU     |
| Aviso 5/2026, carreira especial médica–SIM | ACCE-ALT                    | 57/2025                                      | convencoes/APU     |
| Aviso 6/2026, Condeixa-a-Nova–SINTAP       | ACEP-DELI                   | 50/2022                                      | convencoes/APU     |
| Aviso 7/2026, São Pedro do Sul–SINTAP      | ACEP-ALT                    | 101/2023                                     | convencoes/APU     |
| Aviso 8/2026, Beja–STFPSSRA                | ACEP-ALT                    | 53/2022                                      | convencoes/APU     |
| Aviso 9/2026, Alfândega da Fé–SINTAP       | ACEP-ALT                    | 43/2025                                      | convencoes/APU     |
| BTE 27, ID 331/2026, APAT–FETESE           | CES-VIG                     | Processo DGERT 25859 e publicações referidas | cessacoes_vigencia |
| BTE 27, ID 332/2026, APAT–SIMAMEVIP        | CES-VIG                     | Processo DGERT 25858 e publicações referidas | cessacoes_vigencia |

As referências históricas que não estão no lote são conservadas com estado
`fora_do_lote`. Os processos ficam identificados; não se afirma que foram
obtidos ou verificados os PDFs de base ausentes. A inclusão desses registos
históricos permitirá resolver ligações exatas numa execução futura.

## Resultado no lote real

213 convenções PRI, 21 SPE, **55 APU**, 110 portarias, 9 adesões, 1 acórdão
e **2 cessações**: total **411**. Os 400 nomes anteriormente atribuídos foram
preservados e os hashes dos 411 PDFs foram verificados.

O catálogo anterior está conservado em
`0_gestao/catalogo/copias_seguranca/antes_tipologias_20261016T111927Z`.
O registo da aplicação é `0_gestao/catalogo/tipologias_20261016.json`; a
[evidência dos 11 documentos](tipologias-2026-10-16.json) foi conservada neste repositório.

## Validação e utilização

A suite passou **528 testes**, com **22 ignorados**. Os testes cobrem o índice completo, as nove classificações públicas, cessações,
relações locais e externas, alvos ambíguos, avisos genéricos, preservação dos
tipos originais e atualização do vocabulário local. A wheel foi construída e
inspecionada para confirmar a inclusão do código, JSON e contexto Markdown.
A seleção da família na GUI foi verificada no macOS com uma janela oculta.

Foram convertidos offline quatro PDFs reais: ACEP-ALT, ACCE-ALT, ACEP-DELI e
CES-VIG. A auditoria final foi reaplicada à cache Docling com hashes verificados:
quatro conversões, zero falhas e zero documentos bloqueados. Três ficaram sem
alertas automáticos; a alteração ACEP com articulado manteve um aviso estrutural
para conferência. Ver [resultado do ensaio](conversao-tipologias-2026-10-16.md).

Para cessações e deliberações identificadas pelo nome canónico, a ausência de
cláusulas próprias ou de nota de depósito não é sinal de truncagem. Os restantes
controlos de conteúdo, montantes, tabelas e ordem são mantidos.

Fechar e reabrir a GUI carrega as alterações. **Convenções (inclui ACEP/ACCE)**
inclui agora os nove documentos públicos. **Cessações de vigência** seleciona
essa família; **Todos os documentos IRCT** inclui os 411 PDFs. O lote já foi
organizado; o botão **Organizar PDFs (sem rede)** permite repetir a operação.
