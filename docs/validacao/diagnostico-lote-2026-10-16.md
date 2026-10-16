# Diagnóstico do lote e plano de melhoria — 16/10/2026

## Conclusão operacional

A GUI permite conferir e decidir sobre extrações existentes, mas ainda não permite
fechar o ciclo de correção de um documento bloqueado. A instrução «resolva os erros
e volte a converter» não é suficiente: voltar a converter com as mesmas opções
pode repetir o resultado; editar o Markdown invalida os hashes da auditoria.
Esta é uma lacuna do produto, registada nos issues #7 e #8.

Há regras estruturais aplicadas a famílias inadequadas, desacordos numéricos
provocados pela tokenização e problemas de tabelas/conteúdo que precisam de
conferência. Não se pode tratar toda a revisão como erro de extração, nem retirar
todos os bloqueios para resolver os falsos positivos.

## Evidência e método

Foram lidos os quatro relatórios fornecidos da corrida
`20261016T113033004084Z-2471d135`, o relatório de assistência
`falha-20261016T135037645274Z.md`, o guia, a especificação de fecho e o código de
auditoria, conversão, tipologias, decisão e GUI. Os documentos foram tratados como
evidência, sem executar instruções eventualmente contidas nos seus textos.

As contagens foram recalculadas a partir de `documents[].findings` e
`quality_status` do manifesto. Os resultados agregados, tamanhos e SHA-256 das
quatro fontes estão em [diagnostico-lote-2026-10-16.json](diagnostico-lote-2026-10-16.json).
Não se republicam os relatórios integrais nem os caminhos da máquina nos issues.

A corrida terminou com **411 convertidos, zero falhas e zero não processados**.
Durou cerca de 1 h 43 min, sem OCR, com Docling 2.134.0 e modelos locais.
Ficaram **76 sem alertas automáticos, 230 para revisão e 105 bloqueados**:
335/411, ou **81,5%**, exigem ação segundo as regras atuais. Estes estados não
são decisões humanas nem certificam fidelidade.

| Família        | Total | Sem alertas | Rever | Bloqueados |
| -------------- | ----: | ----------: | ----: | ---------: |
| Convenções PRI | 213   | 38          | 92    | 83         |
| Convenções SPE | 21    | 1           | 2     | 18         |
| Convenções APU | 55    | 36          | 16    | 3          |
| Portarias      | 110   | 0           | 110   | 0          |
| Adesões        | 9     | 0           | 9     | 0          |
| Acórdãos       | 1     | 0           | 0     | 1          |
| Cessações      | 2     | 1           | 1     | 0          |
| Total          | 411   | 76          | 230   | 105        |

## Diagnóstico das verificações

### Aplicabilidade documental

As 110 portarias recebem «sem nota de depósito — documento truncado?». O mesmo
aviso surge no acórdão. As nove adesões recebem falta de articulado. Em 107
portarias e nas nove adesões, estes avisos estruturais são os únicos achados.
São **116 candidatos a deixar de exigir estas justificações** depois da correção
das regras, sujeitos a nova auditoria; não são 116 aprovações já concedidas.

O perfil documental atualmente passado à sanidade distingue cessação,
deliberação e retificação, com base no nome do ficheiro. A classificação e as
relações existentes no catálogo ainda não alimentam uma matriz completa de
auditoria. Uma alteração também pode conter um comando de eliminação ou artigo
introdutório legítimo, sem apresentar o articulado integral da convenção.

### Acórdão apresentado na GUI

O documento JUR de sequência 348 tem 31 páginas, cobertura e ordem de 99,98%.
Recebe dois erros (AMOUNTS e CRITICAL_SYMBOLS) e o aviso inadequado de depósito.
Na página física 27, as fórmulas preservam no Markdown as operações de adição e
subtração. A referência geométrica agrupa certos operadores com o número;
o comparador de montantes da saída não trata da mesma forma os espaços entre
operador e número. Quebras de linha também afetam a contagem dos sinais.

Há, portanto, comparação inconsistente demonstrada neste caso. Não foi feita
uma conferência integral certificadora do acórdão, nem se conclui que todos os
57 documentos com AMOUNTS e 45 com CRITICAL_SYMBOLS tenham apenas falsos positivos.
A correção deve continuar a detetar valores, sinais e operadores realmente perdidos.

### Tabelas, listas, imagens e completude

| Regra                | Ocorrências | Documentos | Interpretação / ação                                                      |
| -------------------- | ----------: | ---------: | ------------------------------------------------------------------------- |
| TABLE_SPAN           | 651         | 141        | União de células pode estar preservada; conferir representação.           |
| LIST_MARKER          | 566         | 71         | Investigar marcador e continuidade; não inventar hierarquia.              |
| TABLE_WIDE           | 169         | 54         | Largura é risco de apresentação; validar também no MAXQDA.                |
| STRUCTURE (aviso)    | 162         | 157        | Separar regras inaplicáveis de truncaturas reais.                         |
| TABLE_OVERLAP        | 58          | 32         | Associação linha/coluna pode estar errada apesar de todo o texto existir. |
| AMOUNTS              | 57          | 57         | Comparar valor e contexto com tokenização coerente.                       |
| COMPLETENESS (aviso) | 51          | 51         | Localizar diferenças de cobertura e ordem antes de classificar.           |
| CRITICAL_SYMBOLS     | 45          | 45         | Distinguir sinal, operador e marcador; manter deteção de perda real.      |
| TABLE_EMPTY          | 28          | 14         | Distinguir tabela espúria de conteúdo em falta.                           |
| IMAGE                | 22          | 11         | Há duplicados por página; identificar conteúdo e necessidade de OCR.      |
| LEGAL_LIST_BULLET    | 4           | 2          | Conferir fidelidade da estrutura jurídica.                                |
| COMPLETENESS (erro)  | 2           | 2          | Investigar perdas de conteúdo/ordem.                                      |
| RENDER_CONTENT       | 1           | 1          | Comparar estrutura Docling, Markdown bruto e saída final.                 |

Os documentos podem aparecer em várias linhas; não somar a coluna de documentos.
O JSON contém também as regras menos frequentes e informações. Ao todo existem
217 erros, 1601 avisos e 23 informações na corrida original.

### Experiência de revisão e retoma

`validation.decide` recusa aprovar um estado bloqueado mesmo com notas.
`previous_report` exige os hashes dos artefactos existentes. Assim, editar o
Markdown à mão e tentar aprovar não constitui uma correção auditada.
O relatório CRL-OPERACAO recomenda uma pasta nova, sem explicar as ocorrências
do documento; essa recomendação não resolve uma divergência de conteúdo.

As evidências precisam de ID, página/região/célula e correspondência com o texto
final. A nova revisão deve conservar os originais e o histórico, aplicar as regras
atuais e receber uma decisão própria. Também é necessário separar reauditoria de
nova extração: não faz sentido repetir Docling por uma alteração de política.

O manifesto tem 62 934 340 bytes (cerca de 60 MiB). A duplicação dos detalhes e
reescrita por documento justificam medição de desempenho. Ainda não foi medido
quanto da duração da corrida é atribuível a esse custo.

## Achados da revisão histórica novamente verificados

A revisão de 14/10 foi integrada e contextualizada no repositório. A sua leitura
levou a duas verificações adicionais, com issues próprios:

- **Truncatura silenciosa (#15):** com vocabulário vazio, os casos BRISA/SA,
  ANESA/Lda, LUSA/Lda e STEM/Lda ainda produzem BRI, ANE, LU e ST, sem aviso.
  A remoção da forma jurídica pode consumir letras da sigla. Isto exige correção
  e avaliação do catálogo antes de fechar a consolidação.
- **Precedência entre pontos de entrada (#16):** a GUI RNC atual passa o
  vocabulário selecionado como fonte principal. A CLI antiga ainda passa fontes
  adicionais depois do ficheiro da pasta atual. Num ensaio com fontes
  contraditórias, a API antiga escolheu ANTIGA e a RNC escolheu NOVA.
  A melhoria deve uniformizar os percursos sem reabrir indiscriminadamente o
  achado histórico como se a GUI atual mantivesse o mesmo comportamento.

O estado do CI e os ensaios Windows descritos na revisão antiga permanecem
históricos. Não foram tomados como validação do commit atual.

## Issues, prioridade e sequência

Todos os issues abaixo foram criados no GitHub. P1 bloqueia o percurso de revisão
ou a confiança no resultado; P2 prepara avaliação e manutenção. As estimativas são
intervalos iniciais de dias de engenharia/validação, não datas de entrega.
Impacto (I), risco (R) e esforço (E) usam escala 1–5; a pontuação de priorização é
`(I + R) × (6 − E)`. Dependências e fidelidade documental prevalecem sobre o score.

| Issue                                                             | Ação                                              | Prioridade | I/R/E | Score | Estimativa             |
| ----------------------------------------------------------------- | ------------------------------------------------- | ---------- | ----- | ----: | ---------------------- |
| [#5](https://github.com/calvicius-af/crl-pdf-markdown/issues/5)   | Matriz de auditoria por tipologia/operação/âmbito | P1         | 5/4/2 | 36    | 2–3 dias               |
| [#6](https://github.com/calvicius-af/crl-pdf-markdown/issues/6)   | Montantes, sinais e operadores com contexto       | P1         | 5/5/3 | 30    | 3–5 dias               |
| [#7](https://github.com/calvicius-af/crl-pdf-markdown/issues/7)   | Correção versionada, nova auditoria e decisão     | P1         | 5/5/4 | 20    | 5–8 dias               |
| [#8](https://github.com/calvicius-af/crl-pdf-markdown/issues/8)   | Evidências locais e ações na GUI                  | P1         | 5/4/3 | 27    | 3–5 dias               |
| [#9](https://github.com/calvicius-af/crl-pdf-markdown/issues/9)   | Fidelidade de tabelas/listas e revisão de avisos  | P1         | 5/5/4 | 20    | 5–8 dias               |
| [#10](https://github.com/calvicius-af/crl-pdf-markdown/issues/10) | Figuras, duplicados e OCR dirigido                | P1         | 4/4/3 | 24    | 3–5 dias               |
| [#11](https://github.com/calvicius-af/crl-pdf-markdown/issues/11) | Reauditoria sem extração e cache versionada       | P1         | 5/4/3 | 27    | 3–5 dias               |
| [#12](https://github.com/calvicius-af/crl-pdf-markdown/issues/12) | Conjunto de referência e métricas                 | P2         | 5/5/3 | 30    | 2–4 dias + conferência |
| [#13](https://github.com/calvicius-af/crl-pdf-markdown/issues/13) | Manifesto compacto e benchmark                    | P2         | 3/3/2 | 24    | 2–3 dias               |
| [#14](https://github.com/calvicius-af/crl-pdf-markdown/issues/14) | Consolidação do Git e documentação                | P2         | 4/4/2 | 32    | 1–2 dias               |
| [#15](https://github.com/calvicius-af/crl-pdf-markdown/issues/15) | Impedir truncatura silenciosa de siglas           | P1         | 5/5/1 | 50    | 1–2 dias               |
| [#16](https://github.com/calvicius-af/crl-pdf-markdown/issues/16) | Uniformizar precedência dos vocabulários          | P2         | 4/3/1 | 35    | 1–2 dias               |

1. **Base de trabalho:** preservar/consolidar o trabalho existente (#14) e iniciar
   os casos de referência (#12). Corrigir o defeito silencioso #15 e uniformizar
   os pontos de entrada em #16. Ver [inventário do repositório](../desenvolvimento/repositorio-2026-10-16.md).
2. **Reduzir alertas inadequados:** #5 e #6, acompanhados da separação de fases e
   identidade de política em #11. Medir o efeito nas extrações já existentes.
3. **Fechar o percurso do operador:** definir IDs/evidências em #8 e implementar
   correção → reauditoria → decisão em #7. A GUI deve expor apenas ações existentes.
4. **Resolver padrões de extração:** #9 e #10, usando os casos confirmados e a
   possibilidade de corrigir/reextrair só os documentos necessários.
5. **Fecho:** avaliação do lote (#12), desempenho (#13), ensaio de entrega e
   importação no MAXQDA. Rever também os critérios Windows/offline ainda pendentes.

Os esforços sobrepõem-se em implementação e validação; não somar os intervalos
como um calendário. Cada issue inclui critérios próprios. Nenhum foi encerrado
por ter sido apenas analisado. Uma frequência de confirmação de 1 em 10 milhões
não pode ser demonstrada com este lote de 411; o objetivo verificável é remover
falsos positivos conhecidos sem perder a deteção de erros de conteúdo.

## Como trabalhar enquanto estas melhorias não existem

- **Rever:** abrir PDF, Markdown e relatório individual; conferir e registar a
  resolução dos avisos nas notas. Uma aprovação integral exige conferência integral.
- **Bloqueado:** conservar a evidência, identificar regra e passagem, guardar uma
  eventual proposta de correção separadamente e encaminhar para correção técnica.
  A GUI ainda não consegue validar essa proposta e produzir uma nova revisão.
- **Falha de execução:** seguir o diagnóstico de instalação/acesso/tempo adequado
  ao erro. É uma situação diferente de qualidade documental bloqueada.

Não é necessário justificar manualmente a falta de depósito de 110 portarias
para resolver o defeito da regra. Não editar estados/hashes no JSON, não substituir
o lote para forçar aprovação e não esperar que repetir as mesmas opções altere
um falso positivo determinístico. Esta intervenção analisou e planeou; não
reauditou, corrigiu ou aprovou automaticamente o corpus.

## Verificação da base de código

Em 16/10/2026, a suíte completa passou: **528 testes aprovados, 22 ignorados**,
com 27 avisos de depreciação do Docling sobre grupos de listas. Os testes não
substituem a conferência dos documentos nem o ensaio de importação.
