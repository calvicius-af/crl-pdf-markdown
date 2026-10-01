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
A interface gráfica requer Tkinter. O conteúdo é processado localmente,
com serviços remotos e plugins externos desativados. Os modelos Docling precisam
de estar disponíveis localmente ou de ser descarregados na primeira utilização.
O OCR está desligado por omissão; usar `--ocr` para digitalizações.

```bash
.venv/bin/python -m crl_markdown convert data/pdfs --out results \
  --models /caminho/modelos-docling --offline --timeout 900
```

A pesquisa de PDFs inclui subpastas, preservadas na saída. Saídas existentes
requerem `--overwrite`. Uma falha não interrompe os restantes documentos.

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

## Saídas e nova renderização

```text
results/documento.md                         ← documento para conferência/importação
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
