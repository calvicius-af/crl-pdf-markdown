# Correções da auditoria e dos casos MAXQDA — 16/10/2026

## Implementação

O trabalho está em `codex/5-auditoria-maxqda`, sobre a integração do PR #4.
Os issues mantêm os critérios de aceitação originais; a implementação não equivale
ao fecho dos ensaios documentais, de distribuição e de importação.

- #5: matriz versionada por família, âmbito e operação, com preferência pelo
  catálogo RNC. Portarias, adesões, acórdãos, alterações públicas, retificações,
  deliberações e cessações deixam de receber exigências próprias de uma convenção
  privada integral. Os controlos de conteúdo permanecem ativos.
- #6: números com espaços, milhares, parênteses e operadores em mudança de linha
  têm comparação consistente. A geometria distingue travessão de célula vizinha
  de sinal negativo. Texto miúdo não mistura valores de linhas adjacentes.
- #7–#8: revisão versionada, editor na GUI, ocorrências com ID/evidência/página,
  filtros e ações de resolução. Cada publicação tem nova auditoria e hashes.
  Editar invalida a decisão anterior; a entrega verifica a revisão ativa.
- #9: reconstrução de grelhas desenhadas quando a correspondência geométrica e
  a conservação dos caracteres o permitem. Células trocadas são verificadas,
  conteúdo sem associação inequívoca permanece bloqueado, avisos repetidos são
  consolidados sem fundir problemas de tabelas diferentes.
- #10: OCR offline apenas das páginas selecionadas, em processo isolado, com
  OCR integral nessas páginas e reutilização verificada das outras. Resolução
  específica de figuras decorativas ou transcritas, com página e fundamento.
- #11: nova corrida de reauditoria sem inicializar os modelos, usando extração
  verificada e políticas atuais. Conserva subpastas, não confunde PDFs com o
  mesmo nome, rejeita cache incompatível e conserva interrupções identificadas.
- #12: comando `evaluate`, comparação por regra/família/estado, hashes e casos
  de referência explícitos; não calcula taxas de erro sem verdade de referência.
- #13: manifesto de índice, com detalhe completo por documento e checkpoint.
  Evidência quantitativa no JSON da comparação e no benchmark sintético separado.
- #14–#16: branch sobre a base consolidada, commits separados, inventário
  preservado; correção de truncatura de siglas e precedência do vocabulário
  explicitamente selecionado na CLI antiga, com regressões e avaliação do catálogo.
- #17: política de hierarquia e regressões dos quatro segmentos MAXQDA.

## MAXQDA: fonte, hierarquia e tabela

O export fornecido tem quatro segmentos em `Sheet1`, linhas 2–5. A referência
versionada é `tests/corpus/maxqda-regressoes.json`, com hash do ficheiro original.
Os campos de posição do export não foram interpretados como páginas do PDF.
O ficheiro Excel e os documentos da corrida original não foram alterados.

A [política de hierarquia](../operacao/hierarquia-markdown.md) estabelece:
`#` identificação; `##` capítulo/anexo de topo; `###` secção no capítulo ou
cláusula diretamente no capítulo; `####` cláusula dentro dessa secção.
Números e alíneas conservam os marcadores publicados. Títulos editoriais gerados
são identificados na proveniência, sem os contar como conteúdo nativo.

No AE 322, o original começa com «Âmbito e vigência», cláusulas 1.ª–3.ª e depois
CAPÍTULO II. A correção usa o título nativo, sem inventar CAPÍTULO I. No INATEL
329, a cláusula 26.ª fica abaixo da SECÇÃO I, que pertence ao CAPÍTULO VI.

As duas tabelas INATEL, nas páginas físicas 2 e 35, tinham categorias e valores
fundidos em grelhas Docling de 41×14 e 22×14. A reparação recupera uma matriz
de 65×15 em cada ocorrência, conservando os caracteres. Os vetores das categorias
Técnico Superior de Grau V e IV são confrontados com os originais nas duas cópias.
Isto não certifica todas as associações da tabela: o carácter «5» sem célula
inequívoca continua separado e gera `TABLE_GRID_GAP`; os rótulos verticais de
grupos profissionais são imagens e continuam a exigir transcrição/OCR e conferência.
O INATEL não é apresentado como documento aprovado.

## Ensaios e limites

A [comparação integral](comparacao-auditoria-2026-10-16.json) usa os mesmos
**411 documentos**, sem falhas e com hashes da origem coincidentes. A reauditoria
terminou em **14 min 13 s**, reutilizando as extrações; a duração anterior de
1 h 43 min incluía a extração e não constitui uma comparação de motores.

| Estado automático | Antes | Depois |
| ----------------- | ----: | -----: |
| Sem alertas       | 76    | 199    |
| Para revisão      | 230   | 122    |
| Bloqueado         | 105   | 90     |

Os 76 documentos anteriormente sem alertas conservaram esse estado. As 9 adesões
e 107 das 110 portarias deixam de ter os avisos estruturais inadequados. O acórdão
348 passa a sem alertas. Há quatro novos bloqueios por desacordo na posição de
células (APEC 124/125, TINITA 198 e ACA 261): o auditor passou a detetar relações
da grelha que a mera contagem de valores não verificava. Não se dispensam essas
divergências sem conferência.

AMOUNTS afeta 18 documentos, contra 57; STRUCTURE afeta 51, contra 173.
Estas diferenças de estado/ocorrências não são uma taxa de falsos positivos
medida. Os critérios definidos para os quatro segmentos MAXQDA passaram nos
dois documentos, incluindo a manutenção do bloqueio legítimo do INATEL.

O manifesto passou de **62 934 340 para 2 448 136 bytes**, mantendo o detalhe
completo em relatórios individuais. Os 411 Markdown originais e o manifesto
original foram verificados por hash depois do ensaio; não foram substituídos.
As amostras de teste ficam em `results/maxqda-amostras-20261016` e o relatório
local completo em `results/avaliacao-final-20261016/comparacao.md`.

- Suíte completa: **583 aprovados, 23 omitidos**, 27 avisos de depreciação Docling.
- Janela Tk nativa em macOS: seleção, editor, bloqueio e disposição dos controlos.
- OCR nativo offline de uma página num PDF de três páginas: apenas a página 2
  foi reextraída; páginas 1 e 3, PDF e Markdown original foram conservados.
  O [registo](ocr-dirigido-2026-10-16.json) distingue este ensaio de uma medição
  da qualidade do reconhecimento de digitalizações.
- OCR real do INATEL: páginas 2 e 35 reextraídas offline, outras 50 reutilizadas.
  O [ensaio](ocr-inatel-2026-10-16.json) concluiu a execução, mas não resolveu
  os rótulos sem transcrição nem o carácter sem célula inequívoca. O bloqueio
  foi mantido. Não se recomenda repetir OCR esperando aprovação automática.
- Wheel construído sem dependências; os perfis JSON/MD fazem parte dos recursos.
- Os [controlos de siglas](impacto-siglas-2026-10-16.json) reproduzem o defeito
  e conferem o catálogo de 411 entradas, sem renomear ficheiros existentes.
- O [benchmark](benchmark-manifesto-2026-10-16.json) usa 50 e 411 registos
  sintéticos em disco local. Não mede desempenho numa partilha nem nova extração.

A reauditoria reutiliza os JSON originais Docling 2.134.0. O ambiente de ensaio
tem Docling 2.128.0; não se apresenta essa reutilização como uma nova extração
dos 411 PDFs na versão instalada. O ensaio OCR usa efetivamente 2.128.0.

Continua pendente o novo ensaio das hierarquias e tabelas complexas no MAXQDA
27.0.0 (a importação básica anterior não valida estas correções) e o ensaio
de distribuição/estação Windows. As amostras são para um projeto de teste; um
documento já codificado não deve ser substituído sem reconciliação das codificações.
Os dois documentos de referência não permitem estimar a taxa de falsos negativos
de todo o corpus nem demonstrar uma confirmação por dez milhões.

Os issues continuam em acompanhamento até revisão e aceitação. Em particular,
o issue #6 precisa da classificação documental dos desacordos remanescentes e de ampliar
o alinhamento contextual para além das comparações atuais; #9 precisa de conferência
de outros padrões de listas e tabelas e de importação; #10 precisa da avaliação
do reconhecimento em digitalizações representativas; #12 precisa de um conjunto
anotado mais amplo, amostragem e medição do esforço humano; #13 conserva pendente
o ensaio numa partilha. A reauditoria atual oferece lote ou documento na CLI;
filtros por família/regra estão na conferência e não num seletor de reauditoria.

Na GUI: escolher a saída antiga, **Reauditar lote**, abrir **Conferir / aprovar…**,
selecionar o documento, **Criar / editar correção**, guardar, **Reauditar correção**
e decidir sobre a versão atual. Consulte o [guia](../operacao/guia-utilizacao.md).
