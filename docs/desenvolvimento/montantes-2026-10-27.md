# Auditoria de montantes — 27/10/2026

Foram investigadas e reauditadas as 18 convenções selecionadas por `AMOUNTS`
e `blocked` na corrida integral de 16/10. Dois defeitos do comparador foram
corrigidos sem alterar os PDFs, os Markdown ou os bloqueios por perdas reais.

## Alterações demonstradas

- **Pontos de preenchimento:** `Almoço/jantar........8,50 €` continha o valor,
  mas a fronteira da expressão numérica impedia reconhecê-lo. Sequências de três
  ou mais pontos passam a separar tokens; `1.250,00` conserva o seu significado.
  O caso ACAP foi conferido visualmente na página física 29.
- **Espaço sobreposto na referência:** na ANACOM, página física 4, um espaço
  escrito sobre o primeiro algarismo fazia o pdfplumber separar `9` e `78,49`.
  A fonte visível e o Markdown apresentam `978,49`. Fragmentos exclusivamente
  numéricos podem agora ser reunidos quando há sobreposição inferior ou igual
  a meio ponto na mesma linha/direção, sem fronteira de célula entre eles.
  Sobreposições maiores e valores de colunas afastadas não são unidos.
- **Localização de evidência:** o relatório procura tokens completos, incluindo
  o sinal. Um desacordo em `-500` deixa de apontar para linhas com `5000`, e
  `8,50` deixa de apontar para `18,50` por coincidência parcial.

Cada regra tem regressões sintéticas que passam por um PDF real. A recuperação
de `978,49` continua a detetar a saída errada `78,49`; a correção dos pontos
continua a detetar a alteração de `8,50` para `18,50`. Os testes também cobrem
fronteiras de células, sobreposição ambígua e evidências com sinais opostos.

## Reauditoria e conservação

Comando executado, sem carregar os modelos de extração:

```bash
PYTHONPATH=src ../crl-app-cct/.venv/bin/python -m crl_markdown reaudit \
  --out results/reauditoria-final-20261016 \
  --destination results/reauditoria-montantes-20261027 \
  --family convencoes --rule AMOUNTS --status blocked --jobs 2
```

| Medida no subconjunto selecionado | Antes | Depois |
| --------------------------------- | ----: | -----: |
| Documentos com AMOUNTS            | 18    | 16     |
| Bloqueados                        | 18    | 17     |
| Para revisão                      | 0     | 1      |
| Sem alertas                       | 0     | 0      |
| Falhas de execução                | 0     | 0      |

A ANACOM passa a revisão. A ACAP deixa de ter AMOUNTS, mas conserva o bloqueio
por sinal/operador ausente. Todos os restantes documentos mantêm os erros.
O código de saída 1 da CLI corresponde a esses bloqueios; não houve falha de execução.

Os 18 documentos reutilizaram extrações verificadas; os hashes dos PDFs e dos
Markdown coincidem com os anteriores. Os **2068 ficheiros** da corrida original
foram conferidos por hash e por inventário antes/depois, sem alterações.
Não foram criadas aprovações humanas.

A [evidência JSON](../validacao/montantes-2026-10-27.json) contém hashes das duas
corridas, identidade da política, resultados e triagem por documento. O relatório
local completo fica em `results/reauditoria-montantes-20261027/_auditoria`.
A suíte local passou **600 testes**, com **23 omissões condicionais** e os 27
avisos Docling existentes. Ruff e Markdownlint passaram.

## Triagem dos casos remanescentes

A classificação abaixo é técnica. A inspeção de contagens e itens Docling não
substitui a conferência integral de grelhas nem permite classificar todos os
restantes alertas como perdas reais já comprovadas.

| Documento / sequência   | Diagnóstico e próximo passo                                                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ACAP 053                | Montante corrigido no auditor; conferir operador `-500` numa fórmula da página 12.                                                  |
| ANF/SIFAP 075           | Categoria, grau e salário fundidos/deslocados. A página 3 confirma colunas distintas; reconstruir a grelha, sem dispensar sinais.   |
| Pestana 077             | Algarismos de milhares e ocorrências em falta nas tabelas; conferir linhas/categorias nas páginas 3, 4 e 7.                         |
| ANACOM 138              | Defeito da referência corrigido; conserva avisos e exige revisão.                                                                   |
| Regantes 146            | Desacordo de uma ocorrência de `920,00`, além de posições de células; falta localizar essa ocorrência.                              |
| LACTICOOP 166/167       | Fórmula `A = VM x 0,75 : 30` guardada em `orig`, com `text` vazio e ausente do Markdown. Recuperar com evidência da fonte.          |
| CITEFORMA 199           | Faltam 20 ocorrências monetárias. Algumas existem noutras linhas; não confundir presença global com conservação de cada ocorrência. |
| Manos Douro 219         | Sequência de sete salários e símbolos euro ausente; conferir linha remuneratória da página 30.                                      |
| REBONAVE 243            | Falta `3 417,46` e um símbolo euro; conferir célula da página 4.                                                                    |
| United European Car 283 | Duas fórmulas fracionárias com `orig` e `text` vazio; recuperar numerador/denominador, sem inventar uma fórmula linear.             |
| SCML 373                | Algarismos iniciais de três salários deslocados para a célula anterior; corrigir associação na página 3.                            |
| Autoestradas 395        | `1 561,00` partido entre células em duas cópias, além de operador ausente; conferir páginas 6, 38 e 11.                             |
| INATEL 413              | Desacordos de contagens e caracteres sem célula inequívoca; manter TABLE_GRID_GAP e conferir categorias.                            |
| CARRISTUR 387–390       | Algarismo de milhares deslocado e sobreposições em grelha rodada; manter bloqueio.                                                  |

O próximo padrão a tratar são as fórmulas: a falta de `text` não deve apagar
silenciosamente um `orig` existente. Contudo, a sequência textual de uma fração
não comprova o seu significado matemático. O percurso deve recuperar só os casos
com geometria/conteúdo demonstrados e tornar os restantes explicitamente visíveis
para correção, incluindo fórmulas sem valores com duas casas decimais.

Os resultados medem estas 18 convenções. A contagem global de 90 bloqueados
continua a pertencer à corrida integral anterior; não foi substituída por uma
extrapolação. A importação MAXQDA e a aceitação Windows/offline continuam pendentes.
