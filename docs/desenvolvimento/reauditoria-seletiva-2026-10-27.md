# Reauditoria seletiva — 27/10/2026

O seguimento do percurso de revisão acrescenta filtros de execução na CLI para
investigar grupos de problemas sem repetir os 411 documentos. A lacuna estava
registada no [balanço anterior](../validacao/correcoes-maxqda-2026-10-16.md).

## Alteração

`reaudit` aceita `--family`, `--rule`, `--status` e o filtro existente `--document`.
Valores repetidos da mesma opção são alternativas; opções diferentes cruzam-se.
A família corresponde à primeira subpasta relativa, em continuidade com a
organização do lote. `.` identifica PDFs na raiz. A seleção usa os achados e
estados registados na corrida anterior; cada PDF recebe todos os controlos atuais.

`--dry-run` mostra os documentos e critérios em JSON, sem abrir PDFs/cache,
carregar modelos ou escrever resultados. Valores desconhecidos, seleções vazias
e documentos sem extração completa dão erro antes da criação do destino.

O manifesto e os relatórios conservam ID/hash da corrida de origem, critérios,
total do lote e caminhos selecionados. A proveniência é escrita desde o primeiro
checkpoint e permanece disponível em corridas interrompidas e nos relatórios
arquivados. A reauditoria cria uma pasta nova e não transfere aprovações humanas.

Ver os comandos no [guia de utilização](../operacao/guia-utilizacao.md#reauditar-uma-seleção-pela-linha-de-comandos).

## Validação

- Suíte completa local: **595 aprovados, 23 omissões condicionais**, com 27 avisos
  de depreciação Docling já existentes. Python 3.11.18, macOS, Docling 2.128.0.
- Testes de seleção: cruzamento/união de filtros, nomes iguais em subpastas,
  PDFs na raiz, filtros inválidos, seleção vazia, extração incompleta, simulação
  sem escrita, execução com um/dois processos e proveniência em interrupções.
- Ruff: código, testes e scripts sem erros. Markdownlint: documentação validada.
- Corpus real: a simulação de `convencoes` + `AMOUNTS` + `blocked` selecionou
  **18 de 411** documentos. Foi executado um desses documentos, ANF/SIFAP 075,
  usando a extração verificada numa pasta nova. Terminou sem falha de execução
  e manteve o estado `blocked`, com AMOUNTS, CRITICAL_SYMBOLS e COMPLETENESS.
- Foram comparados os hashes dos **2068 ficheiros** da corrida original antes
  e depois do ensaio; conteúdo e conjunto de ficheiros ficaram inalterados.

A [evidência JSON](../validacao/reauditoria-seletiva-2026-10-27.json) regista
IDs, hash do manifesto de origem, filtros, contagens e resultado. O diagnóstico
local está em `results/reauditoria-seletiva-20261027/_auditoria/diagnostico.md`.

## Próximo trabalho e limites

Este incremento resolve a seleção de execução prevista no seguimento de #11;
não conclui o issue nem os restantes critérios de aceitação. A GUI conserva a
reauditoria do lote completo e os seus filtros de conferência.

A contagem de 90 bloqueados pertence à reauditoria integral anterior. O ensaio
atual de um documento não altera essa contagem nem mede falsos positivos ou
fidelidade documental. A próxima investigação pode concentrar-se nas 18
convenções com AMOUNTS, classificando os desacordos antes de alterar comparadores.

Continuam pendentes os ensaios das estruturas complexas no MAXQDA e a aceitação
da distribuição na estação Windows/offline. Correções humanas posteriores à
corrida original devem seguir o seu próprio percurso de revisão, sem as substituir
por uma nova renderização da cache Docling.
