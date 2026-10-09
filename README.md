# CRL — PDF para Markdown

Variante de [crl-app-cct](https://github.com/calvicius-af/crl-app-cct), com o
histórico Git preservado, dedicada à importação direta de documentos no MAXQDA.

```text
PDF → Docling → regras de estrutura e leitura do AppCCT → Markdown
                                                       → completude e diagnóstico
```

A versão 0.2 recupera o núcleo de extração, legibilidade e auditoria do projeto
original. Não executa pré-codificação, comparação temática nem geração de QDPX.
O formato documental de trabalho é Markdown; os dados de auditoria ficam à parte.

## Instalar e utilizar

Python 3.11 a 3.13; as estações do CRL usam Windows com Python 3.13. Instalar o
Python de python.org com a opção «tcl/tk and IDLE», necessária à interface
gráfica. No macOS, só há pacotes do PyTorch para Apple Silicon com macOS 14 ou
superior; usar Python arm64.

O ficheiro `requirements/runtime.txt` fixa as versões testadas do Docling, do
PyTorch e das restantes dependências diretas. Usá-lo sempre como `-c`: sem ele,
cada instalação nova recebe a versão mais recente do Docling, que ninguém testou.
Criar o `.venv` num disco local, não numa unidade de rede.

No Windows (PowerShell, a partir da pasta do projeto):

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -e . -c requirements\runtime.txt
.venv\Scripts\python.exe -m crl_markdown convert documento.pdf --out results
.venv\Scripts\python.exe -m crl_markdown convert data\pdfs --out results
.venv\Scripts\python.exe -m crl_markdown.app
```

No macOS e no Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e . -c requirements/runtime.txt
.venv/bin/python -m crl_markdown convert documento.pdf --out results
.venv/bin/python -m crl_markdown convert data/pdfs --out results
.venv/bin/python -m crl_markdown.app
```

Não é preciso ativar o `.venv`: chamar o Python dele diretamente garante que se
usa o interpretador onde as dependências foram instaladas. A conversão é
processada localmente, com serviços remotos e plugins externos desativados. O
OCR está desligado por omissão; usar `--ocr` para digitalizações.

A pesquisa de PDFs inclui subpastas, preservadas na saída. Saídas existentes
requerem `--overwrite`. Uma falha não interrompe os restantes documentos.

## Modelos Docling sem rede

O Docling precisa de modelos (layout, tabelas e, com `--ocr`, o RapidOCR). Sem
`--models`, descarrega-os do Hugging Face na primeira conversão, o que falha
numa rede que bloqueie esse acesso. Nas estações, preparar os modelos uma vez
numa máquina com rede e copiar a pasta inteira:

```powershell
.venv\Scripts\python.exe -m crl_markdown models download --dest C:\caminho\modelos-docling
.venv\Scripts\python.exe -m crl_markdown models verify --folder L:\partilha\modelos-docling
.venv\Scripts\python.exe -m crl_markdown convert data\pdfs --out results --models L:\partilha\modelos-docling --offline --timeout 900
```

```bash
.venv/bin/python -m crl_markdown models download --dest /caminho/modelos-docling
.venv/bin/python -m crl_markdown models verify --folder /caminho/modelos-docling
.venv/bin/python -m crl_markdown convert data/pdfs --out results --models /caminho/modelos-docling --offline --timeout 900
```

O `download` escreve `manifesto_modelos.json`, com o tamanho e o SHA-256 de cada
ficheiro e a versão do Docling. O `verify` confirma a cópia contra o manifesto, e
a conversão repete essa verificação antes de começar: um ficheiro em falta,
alterado ou a mais interrompe a corrida com uma mensagem, em vez de falhar em
cada documento. Descarregar com a mesma versão do Docling que as estações usam
(`requirements/runtime.txt`). `models inventory --folder` reescreve o manifesto
de uma pasta preparada de outra forma.

O OCR usa sempre o RapidOCR com o modelo de português. Não se usa a escolha
automática do Docling, que depende do que está instalado e não do que está na
pasta, e que em modo offline podia ir buscar modelos à rede. Por isso, `--ocr`
com `--offline` exige `--models` com os modelos do OCR, e a conversão recusa-se
a começar sem eles.

## Recolha dos documentos do site do BTE

A recolha foi adaptada de `cct/recolha.py` do projeto original, commit
`9faa8fef3c73d4a853e0c2f6592ce69ac42b7709`. Parte dos índices Excel da DGERT,
com os cabeçalhos de 2025 ou 2026, e descarrega os PDFs individuais das ligações
indicadas. Copiar os índices para `data/raw/indices/` antes de executar:

```powershell
.venv\Scripts\python.exe -m crl_markdown collect --indices data\raw\indices
.venv\Scripts\python.exe -m crl_markdown collect --indices data\raw\indices --confirmar-rede
.venv\Scripts\python.exe -m crl_markdown convert data\raw\bte\bte_2026\convencoes --out results\bte
```

```bash
.venv/bin/python -m crl_markdown collect --indices data/raw/indices
.venv/bin/python -m crl_markdown collect --indices data/raw/indices --confirmar-rede
.venv/bin/python -m crl_markdown convert data/raw/bte/bte_2026/convencoes --out results/bte
```

O primeiro comando simula e escreve o catálogo, sem pedidos de rede. O segundo
ativa as descargas; também pode usar-se a variável `CRL_RECOLHA_REDE=1`
(no PowerShell, `$env:CRL_RECOLHA_REDE = "1"`). A rede fica limitada
a HTTPS nos três anfitriões oficiais reconhecidos pelo projeto original. URLs e
redirecionamentos externos são recusados. Na cloud, permitir esses anfitriões nas
configurações de rede; a conversão requer também modelos locais ou acesso ao
Hugging Face.

Os PDFs mantêm o nome de origem em `data/interim/recolha/ANO/NUMERO/`. O catálogo
`data/registo/registo_bte.jsonl` conserva tipo, título, outorgantes, código IRCT,
URL, estado e SHA-256. Uma segunda corrida não volta a pedir os ficheiros cujo
hash local coincide. Conservar os índices e o catálogo com os PDFs. A escrita é
atómica; falhas e linhas inválidas ficam reportadas e fazem o comando terminar
com código 1. Um PDF local sem hash registado não é substituído por conteúdo
diferente. Ano, número BTE e nome do PDF são obrigatórios, fornecidos no índice
ou derivados da ligação. Índices vazios ou não reconhecidos também falham.

Usar `--destino` e `--registo` para outras pastas; `--familias` seleciona
`convencao,extensao,adesao,acordao,aviso`; `--limite 5` limita documentos pedidos e
`--pausa 1` controla o intervalo entre documentos. Tipos desconhecidos são
registados e reportados, mas não descarregados. Os caminhos por omissão são
relativos à pasta de trabalho. Executar da raiz deste repositório.

Este mecanismo não descobre novos boletins nem descarrega os índices sozinho:
segue o comportamento do original, baseado em índices fornecidos pela equipa.
Também não recorta documentos de boletins históricos completos. A conversão e
auditoria mantêm os comandos existentes.

### Nomes do RNC

No fim de cada recolha, com ou sem rede, os PDFs recolhidos são copiados para
`data/raw/bte/bte_ANO/` com o nome do esquema do RNC (ADR-0022 do AppCCT, de
onde a nomeação foi portada). O Markdown herda o nome do PDF.

| Família              | Pasta                            | Exemplo                                         |
| -------------------- | -------------------------------- | ----------------------------------------------- |
| Convenção            | `convencoes/PRI`, `SPE` ou `APU` | `2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+3`    |
| Portaria de extensão | `portarias_extensao`             | `2026_BTE_01_PE_012_0452-2025_27251_ACRAL-CESP` |
| Acordo de adesão     | `acordos_adesao`                 | `2026_BTE_12_AA_412_27251_ABC-CESP`             |
| Acórdão              | `acordaos`                       | `2026_BTE_05_JUR_101_27251_ACRAL-CESP`          |

O nome começa por ano e número do BTE; o quarto campo é o âmbito numa convenção
ou o tipo nas outras famílias; termina com o código IRCT da convenção de base e
as siglas da primeira parte patronal e da primeira sindical (`+N` conta as
restantes). Os índices que escrevem o tipo por extenso («ADESÃO», «ACORDÃO»)
recebem o mesmo código (`AA`, `JUR`). Os acórdãos usam `JUR`, e não `AC`, para
não se confundirem com ACT nem com acordo. Os avisos ficam só no catálogo.

Um nome atribuído não muda. Por isso, um documento com dados incertos fica
`por_confirmar` e não é copiado: siglas adivinhadas, âmbito proposto por regra
ou pela lista do INE, outorgantes lidos do título, ou o código da convenção de
base lido da cadeia de alterações do índice. Sem código de base, ou sem número e
ano da portaria, nunca há nome. As siglas vêm do registo de organizações da
DGERT (`vocabularios/siglas_organizacoes.csv`) e do `siglas.csv` da equipa, na
pasta de trabalho (`nome;sigla`, com ou sem cabeçalho), que tem prioridade.

O registo da DGERT só tem associações e sindicatos: as siglas de empresas
(acordos de empresa) são adivinhadas e ficam por confirmar. Cada recolha
escreve-as em `data/registo/siglas_pendentes.csv` (`nome;sigla;documentos`),
com os documentos que cada uma bloqueia, os mais frequentes primeiro. Abrir no
Excel, corrigir a coluna `sigla`, apagar as linhas que não estiverem certas e
copiar as restantes para o `siglas.csv` (guardado como CSV separado por ponto e
vírgula, em UTF-8 ou no formato do Excel); repetir a recolha nomeia os
documentos desbloqueados. Depois de rever o resumo, `--aceitar-heuristicas`
nomeia também os restantes. `--nomes` muda a pasta de destino e `--sem-nomear` desliga este passo.

## Utilização com Microsoft Copilot

Ver [a análise de viabilidade](docs/copilot/viabilidade.md), as
[instruções para o agente](docs/copilot/instrucoes-agente.txt) e o
[protótipo de skill](docs/copilot/skill-bte/SKILL.md). O caminho proposto é recolher,
converter e conferir fora do Copilot, depois disponibilizar o corpus aprovado
como conhecimento do agente, preferencialmente em SharePoint. Skills do Agent
Builder existem em preview Frontier; a disponibilidade no II precisa de ser
confirmada. Os scripts dessas skills não têm rede nem instalação de pacotes.

## Regras recuperadas do projeto original

As regras estão em `src/crl_markdown/legacy/`, portadas do commit `53fd77c`.
São usadas efetivamente pelo conversor Markdown, não apenas guardadas como arquivo.

- Ordem de leitura por página, coluna e posição, corrigindo blocos deslocados.
- Limpeza de mobiliário do BTE e reparação de translineação.
- União de referência e título: `Cláusula 1.ª - Área e âmbito`.
- Reconhecimento de capítulos, secções, artigos, anexos, ordinais por extenso,
  cláusulas prévias e texto consolidado, com salvaguardas contra remissões falsas.
- Proteção de títulos longos, linhas de tabela e datas de outorga.
- Preservação dos marcadores legais: `1-`, `2-`, `a)`, `g)`, incluindo marcadores
  em campo separado e números colados ao texto. Não acrescenta balas sobre eles.
- Identificação do preâmbulo e separação das assinaturas, incluindo blocos a meio
  do documento. Os rótulos acrescentados são excluídos da medição de completude.

As divisões de palavras como `ex - ceção` ou `tabe- la` são reparadas antes da
renderização, apenas quando a palavra unida existe na referência independente do
PDF. Os hífenes de palavras compostas e os marcadores legais são preservados.
Sem referência legível, estas reparações não são aplicadas.

Os cabeçalhos, datas da edição e rodapés reconhecidos do BTE são retirados da
referência antes da medição; as citações do boletim no corpo mantêm-se. Resíduos
que permaneçam no Markdown continuam a ser sinalizados. Um pequeno objeto
gráfico centrado nos primeiros 7,5% da altura da página é tratado como logótipo
apenas quando a página tem identificação textual do BTE e a área é inferior a
0,5% da página. Figuras no corpo ou sem esse contexto continuam a gerar avisos.

A exportação nativa `DoclingDocument.export_to_markdown()` fica guardada para
comparação. O documento final é construído a partir dos itens estruturados do
Docling, aplicando as regras acima. Números como `7.` são escapados em Markdown
para que o importador mostre o número original sem o renumerar.

As tabelas usam `table_cells` diretamente: grelhas retangulares, células unidas
emitidas uma só vez e continuações vazias. A versão `.grid` do Docling pode apagar
células quando existem spans sobrepostos. A nova via preserva todos os textos
nesses casos e marca `TABLE_OVERLAP` como erro, pois a posição continua duvidosa.
Grelhas que o Docling confundiu com título e números de uma cláusula são
recuperadas como texto, segundo uma regra estreita testada no caso APSolutions.

## Completude e qualidade

Cada conversão mede o conteúdo visível do **Markdown final** contra uma leitura
independente do PDF com PDFium, reutilizando os controlos do AppCCT:

- Cobertura e excesso de palavras, incluindo as contagens de palavras repetidas.
- Ordem de leitura, trechos em falta e páginas afetadas, palavras invertidas,
  resíduos de cabeçalhos/rodapés e sinais de tabelas colapsadas.
- Comparação de montantes com vírgulas e separadores de milhares, auditada também
  pela geometria das palavras do pdfplumber para não confundir nível e salário.
- Auditoria cruzada de tabelas, anexos remuneratórios, cláusulas sem corpo e
  posição da nota de depósito, com exceções comprovadas para retificações.

A completude herdada considera cobertura de pelo menos 99,5%, excesso até 0,5%
e ordem de pelo menos 97% como requisitos para `OK`; cobertura abaixo de 97%
produz `FALHA`. A perda ou alteração de montantes e a sobreposição de células
produzem erros mesmo quando a cobertura global é elevada.

PDFium pode não ler corretamente certas páginas rodadas; nesses casos, o controlo
herdado usa pdfplumber e identifica as páginas no relatório. A medição dessas
páginas deixa de ser independente. Se não existir camada textual de referência,
a completude do OCR fica por comprovar e é sinalizada como erro.

`quality_status` tem três valores: `passed`, `review` e `blocked`. Os dois últimos
pedem revisão; `blocked` identifica erros que impedem considerar a extração
validada. O Markdown continua disponível como rascunho para conferência, e o
comando termina com código 1 quando existem erros. `--strict` também faz os avisos devolverem código 2.
Informações sobre retificações legítimas não contam como falhas.

## Relatório consolidado por corrida

Todas as execuções, pela linha de comandos ou pela interface gráfica, produzem
um relatório resumido do lote em `_auditoria/diagnostico.md`. A interface inclui o botão
**Abrir relatório do lote**; a linha de comandos mostra o caminho no fim.

- Índice de todos os PDFs, incluindo subpastas, com estado, cobertura, ordem de
  leitura, número de tabelas e contagem de erros e avisos.
- Resumo das regras acionadas e número de documentos afetados.
- Ações de revisão por documento, agrupando ocorrências repetidas da mesma regra.
  A versão completa, com cada linha e mensagem, fica em `_auditoria/detalhes.md`.
- Na versão completa: evidências de completude, palavras e montantes em falta ou excedentes,
  trechos e contextos, perdas por página, referências alternativas, resíduos
  e palavras invertidas, mesmo quando o veredicto global é `OK`.
- Falhas de conversão e documentos não processados numa execução interrompida,
  sem apresentar um Markdown antigo como resultado da tentativa atual.
- Hashes, versões, opções e indicação de reutilização da extração Docling.

`relatorio.txt` conserva o inventário de ocorrências para pesquisa rápida;
`manifest.json` conserva os dados completos de todos os documentos e as datas UTC.
Cada corrida fica arquivada em `_auditoria/corridas/<id>/`, enquanto os
ficheiros diretamente em `_auditoria/` correspondem à corrida mais recente.
Uma nova corrida conserva os relatórios anteriores; os documentos e as auditorias
individuais podem ser substituídos com `--overwrite`, por isso os links dos
relatórios antigos podem apontar para ficheiros entretanto atualizados. Os hashes
arquivados permitem identificar essa diferença.

## Saídas e nova renderização

```text
results/documento.md                                    ← documento para conferência/importação
results/_auditoria/diagnostico.md                       ← resumo e ações de revisão do lote
results/_auditoria/detalhes.md                          ← evidências e ocorrências completas
results/_auditoria/relatorio.txt                        ← inventário de todas as ocorrências
results/_auditoria/manifest.json                        ← dados e proveniência da corrida
results/_auditoria/corridas/<id>/                       ← relatórios de corridas anteriores
results/_auditoria/documentos/documento.docling.md      ← exportação Markdown nativa
results/_auditoria/documentos/documento.docling.json    ← itens e geometria Docling
results/_auditoria/documentos/documento.qualidade.json  ← métricas, estrutura, alertas e hashes
results/_auditoria/documentos/documento.qualidade.md    ← diagnóstico legível
```

Com uma pasta de entrada com subpastas, os Markdown repetem as subpastas e os
ficheiros de auditoria de cada documento ficam em `_auditoria/documentos/`, com
as mesmas subpastas. Os relatórios do lote são escritos logo no início e
atualizados depois de cada documento: uma corrida interrompida deixa o
diagnóstico do que foi feito, com o estado `interrompida`. Repetir a corrida
com a mesma pasta de saída retoma-a: um documento já convertido a partir do
mesmo PDF (mesmo SHA-256) é reaproveitado sem nova extração; um PDF diferente
com saída existente continua a exigir `--overwrite`. As conversões feitas com a
versão anterior, que tinham `_auditoria` em cada pasta, também são
reaproveitadas, e os seus ficheiros de auditoria passam para
`_auditoria/documentos/`. Na interface, fechar a janela durante uma conversão
pede confirmação.

Cada corrida acrescenta a `_auditoria/progresso.log` a hora e o documento em
curso. Se o processo terminar sem mensagem (uma falha numa biblioteca em C ao
ler um PDF fecha a janela sem exceção Python), a última linha diz qual era o
documento, e `_auditoria/falha_nativa.log` guarda o rasto da falha.

Importar apenas o documento final, excluindo `_auditoria`. Os relatórios conservam
os hashes do PDF, do Markdown e dos itens Docling. É possível reaplicar novas
regras a uma extração guardada, sem voltar a carregar os modelos:

```powershell
.venv\Scripts\python.exe -m crl_markdown convert data\pdfs --out results\nova --docling-cache results\anterior
```

```bash
.venv/bin/python -m crl_markdown convert data/pdfs --out results/nova --docling-cache results/anterior
```

O comando verifica os hashes do PDF e da cache, e mede novamente a completude.
Não substitui uma nova extração quando o problema está no reconhecimento Docling.

## Linting e testes

O lint Python verifica a estrutura CommonMark, tabelas, títulos separados,
balas sobre numeração legal, HTML, imagens e Unicode danificado. O normalizador
alinha tabelas e separa títulos e parágrafos. O markdownlint-cli2 verifica as
regras selecionadas de títulos, espaçamento e integridade de tabelas,
sem exigir renumeração de listas nem comprimento máximo de linhas.

```bash
.venv/bin/python -m crl_markdown lint results
npm ci
npx markdownlint-cli2 'results/**/*.md'
.venv/bin/python -m pip install -e '.[dev]' -c requirements/runtime.txt -c requirements/dev.txt
.venv/bin/python -m pytest
.venv/bin/python -m ruff check src tests scripts
npm run lint:md
```

Foram recuperados onze ficheiros de testes do projeto original, cobrindo regras
estruturais, marcadores Docling, sanidade, tabelas, recortes, colunas, numeração e
completude. Foram excluídos os testes exclusivos das fases removidas; os contratos
com o novo pipeline Markdown têm testes próprios.

O CI executa os testes sintéticos e com objetos reais docling-core em Linux,
Windows e macOS, com Python 3.11 e 3.13, sem descarregar modelos nem PDFs. Um job
à parte faz a instalação completa em Windows e macOS com Python 3.13 e as versões
de `requirements/runtime.txt`, e confirma que o conversor arranca. A suite real verifica os 14
PDFs identificados por SHA-256 no manifesto do corpus anterior, com atenção aos
casos ACIBARCELOS, Empresa Metropolitana, IBERCOURIER, AWP, APSolutions e CARRISTUR.

```bash
CRL_TEST_CORPUS=/caminho/pdfs \
CRL_TEST_CACHE=/caminho/extracoes-docling \
CRL_TEST_MODELS=/caminho/modelos-docling \
.venv/bin/python -m pytest
```

As expectativas estruturais vêm do corpus anterior. Os limites de regressão
não certificam completude: os testes também exigem que as falhas conhecidas de
tabelas permaneçam bloqueadas. Não existe uma aprovação automática de documentos
ambíguos só para obter uma suite verde. Ver os resultados em `VALIDACAO.md`.
