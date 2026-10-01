# CRL — PDF para Markdown

Variante de [crl-app-cct](https://github.com/calvicius-af/crl-app-cct), com o
histórico Git preservado, dedicada à preparação de documentos para importação
direta no **MAXQDA**:

```text
PDF → Docling (texto, títulos, listas e tabelas) → normalização → Markdown
                                                          → relatório de revisão
```

Não executa pré-codificação, comparação de versões, triagem temática nem geração
de QDPX. O único formato documental produzido é Markdown. Os relatórios JSON são
auxiliares de controlo de qualidade e não se importam no MAXQDA.

## Instalar

Python 3.11 ou superior. No macOS Apple Silicon, usar Python arm64.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e .
```

No Windows substituir `.venv/bin/python` por `.venv\Scripts\python.exe`.
Docling é a dependência principal; os seus modelos precisam de estar disponíveis
localmente ou de ser descarregados na primeira utilização. O conteúdo dos PDFs é
processado na máquina, com serviços remotos e plugins externos desativados.

## Utilizar

Interface gráfica (requer Tkinter, incluído em muitas distribuições de Python):

```bash
.venv/bin/python -m crl_markdown.app
```

Conversão individual ou de uma pasta, incluindo subpastas:

```bash
.venv/bin/python -m crl_markdown convert documento.pdf --out results
.venv/bin/python -m crl_markdown convert data/pdfs --out results
```

O Docling utiliza reconhecimento de tabelas em modo `ACCURATE`. O OCR está
desligado por omissão para PDFs com camada textual; usar `--ocr` para documentos
digitalizados. `--timeout 900` define o limite por documento em segundos.

Com modelos já preparados, sem descarregamentos:

```bash
.venv/bin/python -m crl_markdown convert data/pdfs --out results \
  --models /caminho/modelos-docling --offline
```

Uma corrida produz, preservando as subpastas da entrada:

```text
results/documento.md                         ← importar este no MAXQDA
results/_auditoria/documento.docling.md      ← exportação original para comparação
results/_auditoria/documento.qualidade.json  ← alertas, versões e hashes SHA-256
```

O comando recusa substituir saídas existentes. Usar `--overwrite` para uma nova
extração. PDFs com nomes que colidem são rejeitados antes da conversão. Uma falha
num PDF não impede a conversão dos restantes; aparece no terminal e causa saída 1.
Conversões parciais do Docling são tratadas como falhas, sem publicar um documento
incompleto. PDFs com problemas estruturais podem gerar Markdown para revisão;
o relatório identifica esses problemas e o comando termina com saída 1.

## Estrutura e linting

A exportação usa diretamente `DoclingDocument.export_to_markdown()`, evitando a
conversão para texto plano do projeto original. O normalizador insere espaços
entre títulos e tabelas, elimina linhas em branco redundantes e alinha tabelas
regulares com pipes. Preserva conteúdo, acentos, montantes, números de cláusulas,
alíneas, quebras explícitas de linha e blocos de código. Não inventa cabeçalhos nem
renumera listas. Se não houver título de nível 1, acrescenta o nome do ficheiro
como título de identificação e regista essa operação no relatório. Substitui
tabulações por espaços fora de blocos de código. Tabelas irregulares ficam
intactas e são sinalizadas.

O validador Python usa um parser CommonMark com suporte de tabelas para detetar
saltos de títulos, tabelas irregulares, HTML, imagens sem transcrição, caracteres
Unicode danificados e extrações vazias. Não é uma implementação completa de
markdownlint. Para a verificação completa das regras selecionadas, usa-se
**markdownlint-cli2**, com a configuração versionada neste repositório:

```bash
.venv/bin/python -m crl_markdown lint results
npm ci
npx markdownlint-cli2 'results/**/*.md'
```

As regras verificam títulos, espaçamento, HTML e integridade/alinhamento de tabelas
(MD055/MD056/MD058/MD060). Não impõem comprimento máximo de linhas, títulos únicos
ou sequência de numeração: esses requisitos poderiam contrariar documentos
extraídos de convenções. `<br>` é permitido pelo markdownlint, mas sinalizado pelo
validador Python para conferir a sua importação. Código sem linguagem e títulos
repetidos são aceites porque podem fazer parte do documento de origem.

Por omissão, avisos permitem saída 0; erros de estrutura e falhas dão saída 1.
`--strict` faz também os avisos produzirem saída 2. `sem_alertas_automaticos`
significa apenas que as verificações passaram, não certifica a fidelidade ao PDF.
Os relatórios guardam a exportação original e os hashes para ajudar a revisão.

## Conferir no MAXQDA

Importar apenas os `.md` finais, excluindo a pasta `_auditoria`. Conferir a ordem
de leitura, as cláusulas e os valores das tabelas contra o PDF. Tabelas com células
unidas não têm representação equivalente em tabelas Markdown simples: o Docling
achata-as e o relatório marca `TABLE_SPAN`. Tabelas largas recebem `TABLE_WIDE`.
Figuras sem texto recebem `IMAGE`. Estes casos requerem revisão humana.

A validação automática verifica a estrutura Markdown; a legibilidade final
depende da versão e do importador do MAXQDA. O exemplo fictício em
`examples/documento.md` permite testar títulos, listas e uma tabela simples.

## Desenvolvimento

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
ruff check src tests
npm ci
npm run lint:md
```

O CI testa Linux, Windows e macOS sem descarregar modelos, incluindo o contrato
com os objetos reais do `docling-core`. O teste de conversão de PDF com modelos
é opt-in: `CRL_TEST_MODELS=/caminho/modelos-docling python -m pytest`.

Referências: [exportação Docling](https://docling-project.github.io/docling/usage/),
[opções de extração](https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md),
[regras markdownlint](https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md).
