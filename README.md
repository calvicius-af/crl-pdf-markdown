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

Python 3.11 ou superior. No macOS Apple Silicon, usar Python arm64.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m crl_markdown convert documento.pdf --out results
.venv/bin/python -m crl_markdown convert data/pdfs --out results
.venv/bin/python -m crl_markdown.app
```

No Windows substituir `.venv/bin/python` por `.venv\Scripts\python.exe`.
A interface gráfica requer Tkinter. A conversão é processada localmente,
com serviços remotos e plugins externos desativados. Os modelos Docling precisam
de estar disponíveis localmente ou de ser descarregados na primeira utilização.
O OCR está desligado por omissão; usar `--ocr` para digitalizações.

```bash
.venv/bin/python -m crl_markdown convert data/pdfs --out results \
  --models /caminho/modelos-docling --offline --timeout 900
```

A pesquisa de PDFs inclui subpastas, preservadas na saída. Saídas existentes
requerem `--overwrite`. Uma falha não interrompe os restantes documentos.

## Recolha dos documentos do site do BTE

A recolha foi adaptada de `cct/recolha.py` do projeto original, commit
`9faa8fef3c73d4a853e0c2f6592ce69ac42b7709`. Parte dos índices Excel da DGERT,
com os cabeçalhos de 2025 ou 2026, e descarrega os PDFs individuais das ligações
indicadas. Copiar os índices para `data/raw/indices/` antes de executar:

```bash
.venv/bin/python -m crl_markdown collect --indices data/raw/indices
.venv/bin/python -m crl_markdown collect --indices data/raw/indices --confirmar-rede
.venv/bin/python -m crl_markdown convert data/interim/recolha --out results/bte
```

O primeiro comando simula e escreve o catálogo, sem pedidos de rede. O segundo
ativa as descargas; também pode usar-se `CRL_RECOLHA_REDE=1`. A rede fica limitada
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
`convencao,extensao,adesao,aviso`; `--limite 5` limita documentos pedidos e
`--pausa 1` controla o intervalo entre documentos. Tipos desconhecidos são
registados e reportados, mas não descarregados. Os caminhos por omissão são
relativos à pasta de trabalho. Executar da raiz deste repositório.

Este mecanismo não descobre novos boletins nem descarrega os índices sozinho:
segue o comportamento do original, baseado em índices fornecidos pela equipa.
Também não recorta documentos de boletins históricos completos. A nomeação RNC
é aplicada no passo separado descrito abaixo. A conversão e auditoria mantêm os comandos existentes.

## Recolher, nomear e converter sem escrever comandos

Com Python 3.11 ou superior instalado (com Tkinter), abrir por duplo clique:

- **Windows:** `scripts/Iniciar.bat`.
- **macOS:** `scripts/Iniciar.command` (Python de python.org recomendado).

O lançador usa o `.venv` do projeto. Se faltarem bibliotecas, apresenta uma
janela para autorizar a instalação e acompanhar o progresso. A primeira
instalação requer Internet; no Linux usa PyTorch para CPU. Node e npm são
necessários apenas para desenvolvimento e lint, não para usar a interface.
Os lançadores precisam de Python instalado; não constituem executáveis autónomos.

A janela tem três passos:

1. **Recolher PDFs:** escolher o índice Excel ou a pasta de índices, a pasta
   dos originais e o registo JSONL. A recolha simula por omissão; as descargas
   exigem marcar a autorização de rede e confirmar na janela.
2. **Rever nomes:** escolher a pasta de destino e, se existirem, os CSV de
   siglas e âmbitos. Carregar em **Preparar / atualizar nomes**, conferir o
   nome original, o nome proposto e os avisos (duplo clique mostra o detalhe).
   Selecionar os documentos aprovados e usar **Aprovar e copiar selecionados**.
   Depois, **Usar esta pasta na conversão** transfere a entrada para o passo 3.
3. **Construir Markdown:** escolher a pasta de saída e os modelos locais.
   **Descarregar modelos…** prepara os modelos Docling, incluindo OCR, com
   autorização de rede. Finalmente, construir o Markdown e abrir o relatório
   do lote para verificar completude e documentos bloqueados.

Cada passo pode ser repetido de forma independente. As operações demoradas
correm fora da thread da janela. Uma falha fica apresentada na interface.
O OCR continua desligado por omissão; só ativá-lo para digitalizações.
O funcionamento offline exige preparar primeiro bibliotecas e modelos.
A cloud sem ambiente gráfico permite testar o pipeline, mas a janela precisa
de uma sessão gráfica local ou de um servidor gráfico disponibilizado pelo host.

### Nomeação RNC entre a recolha e a extração

As regras foram adaptadas do AppCCT, commit
`5fd8ae848d44274306e1414621ddeabc620ca4c6`, incluindo siglas, âmbitos,
referências às convenções de base e separação por família documental.
Um exemplo de nome é `2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP.pdf`.
As cópias ficam em `data/raw/bte/bte_2026/convencoes/PRI/` ou nas pastas
correspondentes à família e âmbito. O conversor Markdown pode ler todas essas
famílias; esta aplicação não realiza codificação temática.

Os PDFs descarregados **mantêm o nome e conteúdo originais**. A nomeação cria
cópias, verifica o SHA-256 da origem, conserva ordinais e regista nome, caminho,
estado e avisos no mesmo JSONL da recolha. Uma cópia existente com o mesmo hash
é reutilizada; conteúdo diferente ou mudança de identidade já atribuída produz
conflito. Propostas derivadas por heurística exigem confirmação individual na
interface. Dados estruturais em falta ou inválidos não são corrigidos pela
aprovação humana. Os CSV podem ser revistos antes de gerar uma nova proposta.

Também disponível pela linha de comandos:

```bash
.venv/bin/python -m crl_markdown rename --registo data/registo/registo_bte.jsonl
.venv/bin/python -m crl_markdown rename --destino data/raw/bte --aplicar
.venv/bin/python -m crl_markdown convert data/raw/bte --out results/bte
```

A simulação grava as propostas no registo mas não copia PDFs. `--siglas` e
`--ambitos` permitem fornecer os CSV da equipa. `--confirmar CHAVE` aprova
um documento específico; é repetível. Avisos do BTE ficam apenas como metadados
no esquema RNC herdado. As restantes famílias só são copiadas com os campos
necessários ao respetivo nome. A recolha continua a partir dos índices fornecidos
pela equipa; não descobre nem descarrega índices automaticamente.

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
results/documento.md                         ← documento para conferência/importação
results/_auditoria/diagnostico.md             ← resumo e ações de revisão do lote
results/_auditoria/detalhes.md                ← evidências e ocorrências completas
results/_auditoria/relatorio.txt              ← inventário de todas as ocorrências
results/_auditoria/manifest.json              ← dados e proveniência da corrida
results/_auditoria/corridas/<id>/             ← relatórios de corridas anteriores
results/_auditoria/documento.docling.md      ← exportação Markdown nativa
results/_auditoria/documento.docling.json    ← itens e geometria Docling
results/_auditoria/documento.qualidade.json  ← métricas, estrutura, alertas e hashes
results/_auditoria/documento.qualidade.md    ← diagnóstico legível
```

Importar apenas o documento final, excluindo `_auditoria`. Os relatórios conservam
os hashes do PDF, do Markdown e dos itens Docling. É possível reaplicar novas
regras a uma extração guardada, sem voltar a carregar os modelos:

```bash
.venv/bin/python -m crl_markdown convert data/pdfs --out results/nova \
  --docling-cache results/anterior
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
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
ruff check src tests
npm run lint:md
```

Foram recuperados onze ficheiros de testes do projeto original, cobrindo regras
estruturais, marcadores Docling, sanidade, tabelas, recortes, colunas, numeração e
completude. Foram excluídos os testes exclusivos das fases removidas; os contratos
com o novo pipeline Markdown têm testes próprios.

O CI executa os testes sintéticos e com objetos reais docling-core em Linux,
Windows e macOS, sem descarregar modelos nem PDFs. A suite real verifica os 14
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
