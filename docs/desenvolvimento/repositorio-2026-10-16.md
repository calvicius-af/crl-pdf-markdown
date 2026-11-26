# Repositório e integração — 16/10/2026

## Linha de trabalho

O desenvolvimento da aplicação PDF → Markdown fica neste repositório.
`crl-app-cct` é fonte de contexto/regras; a pasta de testes não é outro repositório
de desenvolvimento. A linha de consolidação é
`codex/integracao-rnc-20261013`, no
[PR #4](https://github.com/calvicius-af/crl-pdf-markdown/pull/4), mantido em rascunho.
`main` continua a base publicada; não foi feita integração nem versão de distribuição.

O [diagnóstico do lote e roteiro de issues](../validacao/diagnostico-lote-2026-10-16.md)
é a entrada para o próximo trabalho. A organização de 411 PDFs está validada;
a qualidade dos 411 Markdown e o ciclo de correção continuam em desenvolvimento.

## Trabalho preservado e separado

Antes dos commits, foi criada uma cópia temporária do diff binário, dos dez
ficheiros não versionados e do inventário Git, em
`/private/tmp/crl-repo-snapshot-20261016`. A cópia temporária é recuperação auxiliar;
os commits são o registo durável do trabalho.

| Commit                    | Conteúdo                                                                                            |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| `5f1352d`                 | Correção macOS: ignorar metadados Finder na verificação de modelos, com testes.                     |
| `aee0f34`                 | Nomeação automática, famílias IRCT, tipologias públicas, relações, GUI e evidências de organização. |
| `7569e70`                 | Integração por cherry-pick da revisão histórica `4c604c9`, conservando autoria e texto.             |
| Commit desta documentação | Diagnóstico do lote, 12 issues, guia transitório e inventário de integração.                        |

O Ruff corrigiu apenas a ordem de um import em `pipeline.py`. As tabelas dos
documentos novos/alterados foram alinhadas para os controlos Markdown.
Não foram alterados os PDFs, a corrida fornecida, as decisões humanas ou os
estados de qualidade do corpus durante esta análise.

## Inventário de branches, PRs e worktrees

| Referência                           | Situação e destino                                                                                                      |
| ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| `main` / `origin/main`               | Base publicada `c66c139`; conservar até revisão e integração.                                                           |
| `codex/integracao-rnc-20261013`      | Consolidação no PR #4; contém os commits do PR #3 e o trabalho de 16/10.                                                |
| `claude/upbeat-lamport-szw12t`       | PR #3 aberto; ancestral da integração. Preservado até fechar o encadeamento dos PRs.                                    |
| `claude/quirky-cerf-9fr2lb`          | Revisão histórica já integrada por cherry-pick. Branch local/remoto preservado até integração de #4.                    |
| `origin/feat/bte-collection-copilot` | Tem três commits próprios posteriores ao PR #1. Não é seguro removê-lo com base no estado desse PR.                     |
| `codex/finish-rnc`                   | Branch local removido: `2297d01` é ancestral da integração.                                                             |
| Worktree temporário `crl-finish-rnc` | Retirado após verificar ausência de alterações e ficheiros não ignorados. Só continha caches/dependências regeneráveis. |
| `arquivo/2026-10-16/finish-rnc`      | Tag local de recuperação de `2297d01`, além do commit já conservado no histórico da integração.                         |
| `stash@{0}`                          | Preservado: `ceab59f26e2254a7785230ef611d66de48b3963d`, alterações anteriores à integração de 13/10.                    |

Não foram removidos branches remotos, descartados stashes ou reescritos commits
publicados. O PR #3 e o #4 sobrepõem-se: não desenvolver duas versões paralelas
do mesmo percurso. O #4 é o ponto de consolidação; o fecho de #3 e a limpeza remota
ficam para a decisão de integração, com revisão preservada.

### Três commits que exigem decisão explícita

- `03fa015`: acrescenta recolha/revisão por separadores e lançador próprio.
  A integração atual tem GUI e organização RNC diferentes. Comparar o comportamento
  de `acquisition_app.py` e o fluxo de revisão de nomes antes de decidir se há
  funcionalidade a recuperar; não fazer cherry-pick integral sobre a GUI atual.
- `16b15de`: corrige UNC no lançador antigo. A integração tem tratamento UNC no
  instalador offline, mas são pontos de entrada diferentes. Verificar a cobertura
  desejada de instalação online/duplo clique antes de dar a alteração por substituída.
- `598f7c8`: põe dependências Windows em armazenamento local e corrige o ambiente
  do lançador antigo. O instalador atual também isola recursos, mas a equivalência
  de todos os pontos de entrada ainda precisa de ensaio Windows.

### Stash anterior à integração

Contém sete ficheiros: `.gitignore`, README, `app.py`, `cli.py`, `pipeline.py`,
`recolha.py` e `report.py`. A leitura do patch mostra versões iniciais de árvore
RNC, comandos init/name/doctor, diagnóstico e relatórios de recolha, entretanto
presentes numa implementação mais recente. O README inclui o esquema de nomes
antigo. Não aplicar o stash por inteiro: comparar por comportamento e confirmar
que nenhum detalhe exclusivo precisa de regressão antes de o retirar. O stash
fica local, sem publicar uma cópia histórica não revista no GitHub.

## Próximas branches e critérios de integração

1. Reconciliar o trabalho pendente de #14 e manter a descrição do PR #4 alinhada
   com os bloqueios reais. O inventário acima é o início dessa organização.
2. Para cada melhoria, abrir `codex/<numero>-<tema>` a partir da base consolidada
   que contém as tipologias atuais. Exemplos: `codex/5-perfis-auditoria` e
   `codex/6-montantes-contexto`. Não criar agora branches vazios para todos os issues.
3. Manter mudanças focadas, ligadas ao issue e com evidência por caso. Reauditoria
   e correção precisam de contrato comum de revisões/ocorrências antes da GUI final.
4. Antes de integrar, testar a suíte e os casos do issue; comparar o corpus quando
   mudar uma regra de fidelidade. CI verde não substitui validação documental.
5. Só retirar o PR #4 de rascunho quando os critérios relevantes da
   [especificação](../../specs/0001-fecho-documental.md) estiverem cumpridos,
   incluindo os ensaios de estação/Windows e de importação ainda pendentes.
6. Depois da integração, verificar ancestralidade/equivalência antes de remover
   cada branch remoto. Conservar histórico, revisões e eventuais commits exclusivos.

## Verificação de 16/10

- Suíte completa: 528 aprovados, 22 ignorados, 27 avisos de depreciação Docling.
- Ruff: sem ocorrências, após ordenar o import das tipologias.
- Markdown: guias, novo diagnóstico, inventário, contexto e evidências de 16/10
  verificados com as regras do repositório.
- `git diff --check`: sem problemas.
- A validação integral do corpus e a implementação dos issues #5–#13 e #15–#16 não foram
  realizadas nesta intervenção de diagnóstico e organização.
