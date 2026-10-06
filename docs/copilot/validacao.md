# Revisão e validação da recolha BTE e dos recursos Copilot

Revisão de 6 de outubro de 2026, em Linux com Python 3.12.14, Docling 2.134.0,
docling-core 2.99.0, PyTorch 2.14.1+cpu e openpyxl 3.1.5.

## Correções da revisão

- Integração do comando `collect` no parser principal, com argumentos partilhados
  com o módulo autónomo.
- Inclusão de openpyxl nas dependências do projeto e na instalação mínima do CI.
- Inclusão da documentação Copilot no comando de lint executado pelo CI.
- Índices vazios, corrompidos, não reconhecidos ou com linhas inválidas deixam de
  produzir um resultado de sucesso sem informação sobre o problema.
- Recusa de URLs malformados, credenciais em URLs, portas alternativas e
  redirecionamentos externos; validação também antes do transporte injetado.
- Recusa de HTTP 304 sem uma cópia local verificada e preservação de PDFs locais
  sem hash registado quando o conteúdo descarregado é diferente.
- Conservação do hash ao excluir e voltar a incluir uma família documental;
  preservação da folha, página e referências do índice no catálogo.
- Instruções de empacotamento da skill verificadas: `SKILL.md` na raiz e
  `references/modelo-resposta.md` no caminho referenciado.

## Falhas anteriores e verificações retomadas

As falhas iniciais de instalação foram resolvidas usando caches graváveis em
`/workspace/.cache`. A primeira execução de pytest tinha sido iniciada antes de
terminar a instalação de dependências; a suite foi repetida após a instalação.

Os HTTP 403 do BTE e Hugging Face deixaram de ocorrer após a atualização da rede.
Foi executado o teste de recolha real, descarregados os modelos layout/tableformer
e repetido o teste de conversão integral de um PDF sintético com tabela e montantes.

Foi obtido o boletim completo BTE 2/2025 para executar os testes históricos de
extração antes ignorados por ausência desse ficheiro. Os oito testes da seleção
histórica passaram. A instalação mínima usada pelo CI foi também reproduzida num
ambiente virtual separado, sem Docling/PyTorch, com os testes sintéticos aprovados.

Os 14 PDFs de `tests/corpus/manifesto.json` foram descarregados dos URLs oficiais e
cada SHA-256 foi confirmado contra o manifesto. Foram realizadas novas extrações
Docling, conservadas como cache auditada, para executar as regressões do corpus.
Nenhum documento falhou a extração; os estados documentais foram **1 passed,
6 review e 7 blocked**. Estes estados não são contagens de testes: os documentos
com erros conhecidos continuam bloqueados e os avisos continuam a exigir revisão.

A execução integral Linux anterior à correção de caminhos Windows terminou com **389 testes
aprovados, zero falhas e zero testes ignorados**, em 134,70 segundos. Ruff,
verificação de dependências, lint de sete ficheiros Markdown e integridade do ZIP
da skill também passaram. Os 24 avisos de depreciação pertencem ao Docling/Pydantic.

## Correção identificada no CI Windows

O CI encontrou uma falha anterior em `test_failed_documents_reported_and_previous_runs_preserved`:
`relative_source` guardava separadores nativos Windows (`nested\bad.pdf`), enquanto
o contrato dos relatórios esperava `nested/bad.pdf`. O manifesto passa a escrever
os caminhos relativos com separadores `/`, conservando os caminhos absolutos para
acesso local. Foi acrescentado um teste com caminhos Windows que também corre em
Linux. O CI agora produz JUnit e anotações das falhas, sem alterar o resultado do
pytest, para permitir diagnósticos diretamente no PR.

## Comandos de verificação

A partir da raiz do projeto, com os PDFs e a cache previamente preparados:

```bash
CRL_TEST_CORPUS="$PWD/data/corpus-pr-validation" \
CRL_TEST_CACHE="$PWD/results/corpus-pr-validation" \
CRL_TEST_MODELS=/workspace/.cache/docling/models \
CRL_TESTE_REDE=1 HF_HOME=/workspace/.cache/huggingface OMP_NUM_THREADS=2 \
.venv/bin/python -m pytest -q -rs
.venv/bin/ruff check src tests
.venv/bin/python -m pip check
npm run lint:md
```

Os PDFs, modelos, cache e resultados são locais e não entram no commit. Para
repetir noutra máquina, obter os PDFs pelos URLs e nomes do manifesto, verificar
os hashes e gerar a cache com `convert --models CAMINHO --offline`. A conversão
pode terminar com código 1 devido aos estados `blocked`; os relatórios explicam
as ocorrências. O CI normal continua sem rede, modelos ou corpus e identifica
esses testes opcionais como ignorados.

## Limitações mantidas

A aceitação e execução da skill no tenant do II não foram verificadas. As fontes
oficiais, os limites e o procedimento do piloto constam de `viabilidade.md`.

O teste manual QDPX/MaxQDA de 2 de outubro continua a registar perda de formatação e
valores de variáveis não atribuídos. Não existe MaxQDA neste ambiente para repetir
a importação; os ficheiros experimentais desse teste não são versionados. Esta
recolha não altera o exportador QDPX nem demonstra uma correção do importador.
Consultar o [registo original](../validacao/teste-md-qdpx-maxqda-2026-10-02.md).
