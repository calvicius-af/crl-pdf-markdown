# Validação inicial — 1 de outubro de 2026

Ambiente local: macOS arm64, Python 3.11.16, Docling 2.128.0,
markdownlint-cli2 0.23.3. Modelos locais; conversão executada em modo offline,
sem OCR e com reconhecimento de tabelas em modo ACCURATE.

## Verificações

- Testes de estrutura: conteúdo de células, montantes e acentos preservados;
  escapes, células vazias, alinhamento e blocos de código tratados corretamente.
- Testes com objetos reais do docling-core: exportação, relatório, recusa de
  sobrescrita, deteção de células unidas e rejeição de documento vazio.
- Testes de lote: subpastas preservadas, continuação após uma falha e deteção de
  colisões de nomes (este último não se aplica a volumes que ignoram maiúsculas).
- Conversão real de PDF sintético: tabela reconhecida, montantes `1250,00` e
  `1000,00` presentes no Markdown final. Teste opt-in com modelos locais.
- Ruff: sem erros. markdownlint: sem problemas no exemplo e nos dois documentos
  reais após normalização. Esta verificação mede sintaxe e estrutura, não
  fidelidade documental.

## Documentos reais

| Documento do BTE 31/2026 | Páginas | Tabelas | Alertas no relatório final |
| ------------------------ | ------- | ------- | -------------------------- |
| CNIS–FNSTFPS, alteração  | 2       | 0       | 2 figuras sem transcrição  |
| AEVP–FESAHT, alteração   | 3       | 1       | 3 figuras sem transcrição  |

A tabela AEVP–FESAHT foi exportada com três colunas e onze linhas de dados;
os grupos I a XI e os valores salariais estão presentes. Não foi feita uma
verificação célula a célula contra o PDF nem uma importação nesta sessão no
MAXQDA. A ordem de leitura e as figuras continuam a exigir conferência humana.

Os PDFs e as extrações reais permanecem locais, em `results/validacao/`, excluídos
do Git. O exemplo público em `examples/documento.md` é fictício.
