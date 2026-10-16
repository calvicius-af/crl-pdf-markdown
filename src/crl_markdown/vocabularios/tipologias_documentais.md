# Tipologias documentais: avisos públicos e cessações de vigência

Decisão funcional do utilizador em 16/10/2026. Aplicada através de
`tipologias_documentais.json`, versão `2026-10-16.1`. Esta convenção interna
não altera a designação publicada pela DGERT/DGAEP nem afirma que essas
entidades tenham adotado novos códigos.

## Dois campos diferentes

`tipo` conserva literalmente o tipo do índice, por exemplo `AVISO` ou
`AV-CES-VIG`. `tipo_documental` descreve a natureza identificada pelos metadados.
O catálogo conserva também a regra, versão, âmbito, operação, referência do
acordo de base, existência de texto consolidado e origem dos outorgantes.

No setor público, o rótulo editorial «Aviso» pode publicar uma alteração de
acordo ou uma deliberação. Não implica que o PDF seja apenas metadados.

| Evidência nos metadados                                              | Tipo documental interno | Família / destino             |
| -------------------------------------------------------------------- | ----------------------- | ----------------------------- |
| Alteração de acordo coletivo e empregador público identificado       | ACEP-ALT                | convencao / convencoes/APU    |
| Alteração de acordo de carreira especial                             | ACCE-ALT                | convencao / convencoes/APU    |
| Deliberação da comissão paritária de ACEP                            | ACEP-DELI               | convencao / convencoes/APU    |
| Deliberação da comissão paritária de ACCE                            | ACCE-DELI               | convencao / convencoes/APU    |
| Cessação/caducidade de vigência, expressa no tipo ou título do aviso | CES-VIG                 | cessacao / cessacoes_vigencia |
| Outro aviso, sem evidência suficiente para os casos anteriores       | AVISO/AV                | aviso / avisos                |

Alterações com texto consolidado mantêm o tipo ALT e registam
`texto_consolidado=true`. As deliberações têm operação própria, para permitir
distinguir interpretação/deliberação de alteração de redação. Os acordos e as
suas alterações continuam documentos autónomos: o sistema não incorpora
automaticamente uma alteração no texto do acordo de base.

## Critérios e precedência

As regras exigem a ação no título e contexto público explícito nos metadados:
município, freguesia, empregador público, ACEP, carreira especial ou ACCE.
Também exigem que o título se refira a um acordo coletivo. A regra de ACCE
precede a de ACEP, para não classificar uma carreira especial como acordo de
um empregador público singular. «Aviso de alteração do horário de atendimento
do Município» e projetos de portaria não são alterações de ACEP.

O número/ano do acordo é retirado de título, documento alterado ou documento
em vigor, por essa ordem. Aceitam-se as grafias coletivo/colectivo. Sem código
DGERT, usa-se uma referência legível como `ACEP53-2016` ou `ACCE57-2025`,
conservando o campo do código DGERT vazio. O ID da nova publicação continua
no nome; não é substituído pelo ID da base.

Os outorgantes são conservados quando vêm preenchidos e, nestes avisos,
podem ser obtidos dos dois lados explicitamente escritos no título. A origem
é registada. Ausência de evidência suficiente mantém a natureza genérica do
aviso; não autoriza inventar partes nem uma ligação documental.

## Relações com o processo original

`processo_irct` identifica o processo documental por código DGERT explícito,
como `DGERT:25859`, ou pela referência pública, como `APU:ACEP:53/2016`.
É um identificador interno de agrupamento, não um novo identificador oficial.

`relacoes_documentais` conserva cada referência e a sua origem. Para referências
BTE, a ligação local exige tipo e ID/ano exatos. Para acordos públicos usa-se
a referência publicada e o tipo ACEP/ACCE; para avisos anteriores pode usar-se
o número/ano publicado no título. Nunca se escolhe arbitrariamente entre dois
documentos candidatos.

- `ligado`: existe uma correspondência única no lote; regista `alvo_chave`.
- `fora_do_lote`: a referência é conservada, mas o alvo não está disponível no lote.
- `ambiguo`: há vários candidatos; conserva-se a referência sem escolher um alvo.

As cessações guardam todas as publicações referidas, incluindo as alterações,
com a relação `cessa_vigencia_de`. Não se fazem novas descargas nem se deduz
uma data de cessação apenas da data do BTE ou do DR. A data juridicamente
relevante deve ser lida no aviso; a classificação não a substitui.

O catálogo JSON de relações é `0_gestao/catalogo/relacoes_documentais.json`.
O catálogo CSV anual inclui as mesmas relações em JSON na respetiva coluna.
Pode ligar-se um alvo histórico mais tarde, repetindo a organização com esse
documento presente no registo.

## Conversão e auditoria

Na GUI, as alterações/deliberações entram em **Convenções (inclui ACEP/ACCE)**.
As cessações podem ser escolhidas em **Cessações de vigência**. **Todos os
documentos IRCT** inclui todas as famílias. Na CLI, usar `convert --workspace
PASTA --familia cessacao` ou `--familia todos`.

Uma cessação ou deliberação pode não ter articulado próprio. Quando o nome
canónico identifica essa tipologia, zero cláusulas gera informação, em vez de
um pedido de revisão por ausência de estrutura. Também não se exige a nota de
depósito própria de uma convenção. Cobertura, ordem de leitura,
montantes, tabelas e conteúdo perdido continuam a ser verificados. Alterações
com articulado e documentos de natureza desconhecida mantêm os controlos
estruturais habituais. A aprovação humana do texto convertido permanece separada.

## Casos do índice fornecido

Avisos 1, 2, 3, 4, 7, 8 e 9/2026: ACEP-ALT. Aviso 5/2026, carreira especial
médica: ACCE-ALT. Aviso 6/2026, comissão paritária de Condeixa-a-Nova:
ACEP-DELI. Publicações 331/2026 (APAT–FETESE) e 332/2026 (APAT–SIMAMEVIP):
CES-VIG, ligadas aos processos DGERT 25859 e 25858 e às publicações históricas
expressamente referidas no índice.
