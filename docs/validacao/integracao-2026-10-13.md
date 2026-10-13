# Integração da nota e das fontes — 13/10/2026

Registo histórico da primeira integração. A [consolidação posterior](fecho-2026-10-13.md)
atualiza nomes, siglas e estado das verificações; as contagens abaixo descrevem esse momento.

## Local correto e âmbito

A nota inicialmente analisada em `crl-app-cct` pertence a `crl-pdf-markdown`.
A especificação foi reescrita para este fork, que já tinha Markdown, cache Docling,
geometria persistente e auditoria. O AppCCT foi usado apenas como contexto e fonte
complementar. A documentação fornecida e resultados anteriores foram conservados.

## Fontes lidas

README do fork, README RNC v4.0, validações locais/Copilot, os dois índices BTE,
o export DGERT e CSV de listas. Inspeção das seis folhas do export; consolidação
das folhas de organizações. Os índices têm 14 entradas no BTE31 e 411 no ficheiro
01–10. A lista CSV contém colunas independentes e quebras literais `\r\n`.

Complementos copiados do AppCCT, commit `53fd77c1f18bf41d35e988ad36e49c855ed209b5`:
organizações, empregadores/âmbito, atos de negociação, tipos e lista INE.
As fontes de siglas e hashes estão no manifesto da consolidação.

## Alterações

- Comandos init/name e opção workspace; árvore RNC adaptada a Markdown.
- Nomeação v4.0 para convenções, cópia verificada e conservação de originais.
- Catálogo por ano, preservando colunas/notas de equipa quando existe chave estável.
- CSV de siglas e script reproduzível, com propostas e ambiguidades separadas.
- Verificação doctor, pacote/instalador offline e lançador com modelos locais.
- Falhas com instruções de recuperação e traceback arquivado; relatórios de recolha.
- Guias de operação/apoio, especificação de fecho e modelo metodológico.

## Consolidação de siglas

3 648 entradas de denominações/variantes, não 3 648 organizações distintas:
1 891 documentadas nas fontes, 1 738 por confirmar e 19 ambíguas.
As propostas não são usadas automaticamente. Nenhuma nova confirmação humana
foi simulada. O ficheiro inclui organizações históricas e nomes de empresas que
não têm sigla oficial no registo; estas lacunas continuam visíveis.

Na prova de metadados do BTE31, seis nomes de convenções são geráveis com as
entradas documentadas; quatro exigem confirmação de siglas e quatro têm os
outorgantes ausentes no índice. Esta prova não descarregou nem nomeou PDFs reais.

## Verificação desta intervenção

Suite local: **379 testes aprovados, 22 condicionais ignorados**. Os testes
omitidos exigem corpus/cache/rede ou condições do sistema de ficheiros.
Foram acrescentados testes de nomes v4.0, recusa de sigla/ID/âmbito inválidos,
preservação de originais/hash, colisão, notas humanas do catálogo, relatórios de
falha, integridade do pacote e colisões entre linhagens documentadas no CSV.

Ambiente de verificação: macOS, Python 3.11 do ambiente existente do AppCCT,
com PYTHONPATH apontado exclusivamente para o `src` deste fork. Não se instalou
este fork naquele ambiente; testes não representam uma instalação nova com todas
as versões fixadas atuais. A própria aplicação não importa nem depende do AppCCT.

Além da suite, verificar sintaxe dos Python, referências locais dos documentos
novos e geração repetida de siglas com hash idêntico. Os testes não demonstram
renderização visual da interface ou utilização no MaxQDA.

## Gates ainda pendentes

- Preparar wheelhouse/modelos e instalar realmente offline numa estação Windows
  3.13, incluindo unidade mapeada/UNC e caminhos com espaços.
- Conferir modelos completos e uma conversão offline real, incluindo OCR se usado.
- Confirmar siglas, âmbito e metadados finais das restantes famílias PE/AA.
- Conferir o corpus e resolver os bloqueios reais de tabelas já registados.
- Validar importação direta Markdown na versão MaxQDA da equipa.
- Implementar decisão humana/promoção por hash, registo completo de alterações
  e geração do relatório metodológico a partir dos resultados reais.

Não foram feitas novas descargas, migrações de dados, alterações no SharePoint,
instalações nas estações, publicações, commits ou pedidos de revisão externos.

Foi criada localmente a árvore `RNC_Dados_2026`, com cópias verificadas dos índices,
export de organizações, lista CSV e procedimento fornecido. O manifesto
`0_gestao/catalogo/fontes_recebidas.json` liga cada cópia à origem e hash.
A recolha em simulação leu 425 entradas, sem pedidos de rede. Nove tipos escritos
«ADESÃO» motivaram um alias para a família adesao e um teste de regressão.
O tipo «ACORDÃO» continua desconhecido e reportado; não foi classificado por inferência.
Os PDFs continuam por descarregar. O catálogo e o relatório de nomeação identificam
as pendências; criar a árvore não significa preparar ou aprovar os documentos.

As 425 linhas correspondem a **411 documentos únicos**: as 14 entradas do BTE31
também constam do índice agregado. A comparação de ID, tipo, código IRCT, título
e outorgantes não encontrou divergências nessas repetições. O registo/catálogo
tem 411 chaves; o resumo por ficheiro conserva as 425 linhas recebidas. Após o
alias ADESÃO, ficam 424 linhas por descarregar e uma linha ACORDÃO ignorada por
tipo desconhecido; não são 424 documentos únicos. O catálogo de nomeação tem
411 pendências, porque não foram recolhidos os PDF nesta intervenção.
