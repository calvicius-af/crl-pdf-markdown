# Revisão e consolidação — 27/10/2026

A revisão concentrou-se nos incrementos locais de seleção/reauditoria e montantes,
no contrato com a cache, na preservação de revisões humanas e nas dependências
entre os três PRs e os 13 issues abertos. Não é uma auditoria exaustiva de todas
as linhas dos PRs históricos nem uma aceitação do produto em estação.

## Achado corrigido: identidade da cache selecionada (P1)

`CachedConverter(records=...)` usava o manifesto apenas para localizar os
ficheiros. Verificava o PDF e o JSON Docling contra o relatório individual,
mas não comparava esses hashes com o registo selecionado no manifesto.
O percurso paralelo descartava os hashes antes de enviar o trabalho ao processo.

Reprodução: conservar o manifesto, substituir o PDF ou a extração Docling e
atualizar os hashes do relatório individual. A cache é internamente consistente,
mas pertence a outra versão. A reauditoria aceitava-a sob os critérios/identidade
da corrida anterior. As quatro regressões iniciais falharam antes da correção.

Correção mínima: conservar os dois hashes do manifesto e compará-los com o
relatório individual antes de reutilizar o documento. O processo paralelo recebe
os mesmos hashes. Hash ausente não concede uma verificação implícita. A falha
fica localizada nesse documento e os restantes continuam a ser processados.

Validação: seis cenários (PDF substituído, extração substituída, hash ausente,
cada um com um/dois processos). Suíte completa: **606 aprovados, 23 omissões**,
com os 27 avisos Docling existentes. Ruff, Markdownlint e verificação do diff
passaram. A correção não introduz dependências, formatos ou motores de extração.

## Resultado por dimensão

- **Correção/integridade:** risco P1 acima corrigido; seleção vazia/inválida,
  fronteiras de células, sinais e bloqueios conhecidos têm regressões.
- **Segurança dos ficheiros:** destinos novos, verificação de caminhos e hashes,
  simulação sem escrita e conservação dos originais mantidos. Sem novos achados
  na superfície revista; não equivale a uma auditoria de segurança integral.
- **Desempenho:** mantidos um/dois processos e índices compactos; só dois hashes
  adicionais são transportados por documento. Não foi criada uma abstração de
  tarefas, serviço ou sistema de filas.
- **Manutenção:** commits por objetivo, reutilização dos percursos existentes,
  sem nova GUI de filtros nem novo motor para fórmulas. São medidas já pedidas
  em #6/#11 e uma correção do contrato existente.

Os controlos existentes já conservavam os originais, validavam o conteúdo da
cache e bloqueavam perdas reais. A revisão acrescenta a ligação que faltava ao
manifesto selecionado, sem substituir esses controlos.

## Linha de integração e PRs

A consulta ao GitHub confirmou os PRs #3, #4 e #18 abertos, sem conflitos de
integração reportados. A ausência de conflitos não substitui revisão ou CI.
A ancestralidade foi novamente verificada após `git fetch origin`:

- #3, `82beb58`: zero commits exclusivos relativamente ao ramo do #4. O #4
  contém integralmente o #3; o encerramento como substituído evita duas vias de
  integração. O branch fica conservado e não se apresenta o PR como integrado.
- #4, `9070ad6`: linha de consolidação destinada a `main`, mantida em rascunho.
- #18: ramo `codex/5-auditoria-maxqda`, baseado no #4. Recebe os incrementos
  de #11 (seleção/proveniência/cache) e #6 (montantes), em commits distintos.
  Permanece em rascunho; deve ser integrado no #4 antes da revisão final de #4.

Não houve integração em `main`, rebase de commits publicados, force push,
remoção de branches, aprovação automática ou encerramento de issues por mera
publicação de código. O CI do commit novo deve ser consultado no GitHub; os
resultados de `85ab53b` pertencem à base anterior.

## Referências históricas preservadas

Foram inspecionados os três commits exclusivos de
`origin/feat/bte-collection-copilot` e os sete diffs rastreados do stash:

- `03fa015`: nomeação, localização e GUI guiada. O percurso atual já tem
  nomeação/organização RNC e GUI; os módulos antigos de aquisição/localização
  constituem uma via alternativa, não uma dependência da correção atual.
  Não foram portados nem declarados equivalentes linha a linha.
- `16b15de`: instalação por GUI e UNC. O instalador atual tem percurso offline
  próprio e testes de referências UNC; não se reintroduziu o lançador antigo.
- `598f7c8`: ambiente por projeto em armazenamento local Windows. O instalador
  atual usa instalação local por utilizador; a aceitação numa estação real
  continua pendente. O commit histórico fica disponível para consulta.
- `stash@{0}` (`ceab59f`): os sete diffs incluem `.gitignore`, README, GUI, CLI,
  pipeline, recolha e relatórios. As funções têm sucessores no ramo atual; o
  esquema de nomes RNC v4.0 desse README foi substituído por decisão explícita.
  Aplicar o stash inteiro voltaria a introduzir opções/documentação antigas.
- Os 30 ficheiros não rastreados guardados no stash continuam presentes na árvore
  atual: 12 coincidem byte a byte e 18 evoluíram. Isto comprova presença, não
  equivalência funcional de todos os diffs; o stash não foi descartado.

Não são necessários cherry-picks ou um segundo lançador para os incrementos
atuais. As referências históricas permanecem preservadas; uma eventual remoção
exigirá demonstração de equivalência ou decisão explícita de abandono.

## Pendências por issue

O issue #6 mantém o alinhamento contextual amplo e classificação dos casos restantes;
O #11 recebe seleção e controlo da identidade da cache, sem reivindicar fecho de
todos os seus critérios; #14 regista esta consolidação e o destino conservador
das referências. Os restantes issues conservam o âmbito e aceitação existentes.

Próximo incremento funcional: tornar explícitas e tratar as fórmulas sem texto
já identificadas no corpus, com prova da sua estrutura. Não iniciar outro motor
de OCR nem reconstrução matemática especulativa. MAXQDA, Windows/offline e
partilha continuam critérios de aceitação distintos dos testes e do CI.
