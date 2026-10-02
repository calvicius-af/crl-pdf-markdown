# Teste Markdown → QDPX → MaxQDA — 2 de outubro de 2026

**Resultado: não aprovado para preservar a formatação e atribuir os metadados.**
Retorno do utilizador em 2026-10-02, após a importação manual no MaxQDA.

## Observações na aplicação

O utilizador comunicou:

> Os MD perdem a formatação na importação para MaxQDA, as variáveis existem mas aparecem sem valores atribuídos aos casos/documentos.

As definições das variáveis foram reconhecidas, mas os respetivos valores não
ficaram atribuídos. A apresentação documental também não preservou a formatação
esperada. A versão do MaxQDA e os elementos concretos de formatação afetados não
foram registados; não existem capturas de ecrã associadas a este teste.

Este registo refere-se à experiência QDPX construída a partir dos Markdown.
Não constitui uma nova verificação separada da importação direta de ficheiros MD,
nem estabelece a causa técnica dos dois problemas observados.

## Entradas e ficheiro testado

- Markdown: os 14 documentos corrigidos de `results/relatorio-revisto/`,
  correspondentes aos IDs BTE 377/2026 a 390/2026; auditorias excluídas.
- Índice: `data/raw/indices/BTE31_2026.xlsx`, do repositório original `crl-app-cct`.
- Pacote: [teste_md_bte31_2026.qdpx](../../results/teste_md_bte31_2026.qdpx).
- Proveniência: [manifesto JSON](../../results/teste_md_bte31_2026.manifest.json),
  com hashes das entradas, cruzamento de linhas do XLSX e validações.

SHA-256 do QDPX testado:

```text
39afa393a455ca73fd8d4cc17f8c7b46f1e7e7a2d76148e092ca01673e2726a8
```

Os artefactos de `results/` são locais e não são publicados no Git.

## Construção da experiência

O exportador do repositório original produziu 14 fontes sem pré-codificação.
Cada fonte contém texto UTF-8 e uma representação DOCX renderizada do Markdown,
com títulos e 47 tabelas no conjunto. O QDPX não contém os Markdown como fontes
nativas: são as representações derivadas que chegam ao importador.

Foram declaradas seis variáveis textuais: `Tipo_documento`, `Subtipo_documento`,
`Tipo_registo_BTE`, `ID_BTE`, `Codigo_IRCT` e `Titulo_BTE`. Os valores constam de
`VariableValue` em 14 casos sem nome, cada um ligado a uma fonte por `SourceRef`.
A importação não confirmou que esta representação atribua valores no MaxQDA.

O tipo base corresponde a `AE` ou `CCT`; `Tipo_registo_BTE` conserva o código
composto original, como `AE-ALT-RECT`. O subtipo descritivo foi lido do título do
XLSX, porque a segunda coluna de tipo está vazia. Para IBERCOURIER (383/2026),
ficou `Não indicado no índice`, sem inferir uma primeira convenção.

## Validações e conclusão

Passaram os controlos de ZIP, XML contra o esquema REFI-QDA, integridade de GUIDs,
preservação das palavras e ordem do Markdown na representação textual, conteúdo
e contagem de tabelas DOCX, e correspondência dos 14 documentos com o XLSX.

Esses controlos não demonstram a apresentação e a atribuição de variáveis no
MaxQDA. O resultado manual prevalece: **formatação perdida e valores não
atribuídos**, apesar de estarem presentes no pacote. O manifesto foi atualizado
com este retorno; os resultados dos controlos técnicos foram conservados.

A experiência permanece separada do pipeline PDF → Markdown. Uma eventual
repetição deve verificar separadamente a apresentação DOCX/TXT escolhida pelo
importador e a associação das variáveis às fontes/casos, comparando a estrutura
com um QDPX exportado pelo próprio MaxQDA. Não foi implementada uma correção nesta
fase de documentação.
