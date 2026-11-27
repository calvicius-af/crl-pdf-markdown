# Variáveis de documento para o MAXQDA: tipologia, regras e exemplos para validação

Estado: proposta para validação, sem implementação. Data: 2026-11-25, revista a 2026-11-26.
As respostas de 2026-11-26 e a revisão das regras do RNC estão na secção 10.
Complementa [analise-variaveis-documento.md](analise-variaveis-documento.md).

Base de trabalho: folha `BTE` do livro `2026_RNC_vardoc_20261123.xlsx` (411 documentos do
BTE 1 a 41 de 2026), folha `Listas`, tabelas do Copilot, `lista_siglas_global.csv`
(6089 entidades) e o ficheiro de variáveis de 2025.

## 1. Decisões registadas

1. Nomes segundo o esquema RNC aprovado (ADR-0022, SPEC-0004).
2. O subtipo descritivo é extraído do título.
3. Todos os tipos de documento podem entrar no MAXQDA; pode haver um XLSX por tipologia.
4. As siglas vêm de `lista_siglas_global.csv`.
5. MAXQDA versão 27.
6. `e texto consolidado` e `/ texto consolidado` são subtipos distintos.
7. Os valores de texto ficam limitados em número de caracteres.

## 2. Tipos presentes no índice de 2026 (facto)

| TipoSubTipoDoc | N   | Com outorgantes | Com CodigoGEPDGERT | Família atual na aplicação                                  |
| -------------- | --- | --------------- | ------------------ | ----------------------------------------------------------- |
| PE             | 108 | 0               | 108                | extensão                                                    |
| AE-ALT         | 80  | 80              | 80                 | convenção                                                   |
| CCT-ALT        | 68  | 68              | 68                 | convenção                                                   |
| ACT            | 55  | 55              | 9                  | convenção                                                   |
| CCT            | 29  | 29              | 29                 | convenção                                                   |
| AE             | 17  | 17              | 17                 | convenção                                                   |
| ACT-ALT        | 15  | 15              | 15                 | convenção                                                   |
| ADESÃO         | 9   | 9               | 9                  | **ignorado** (a aplicação espera `AA`); corrigido em `main` |
| AVISO          | 9   | 9               | 0                  | aviso                                                       |
| AE-ALT-RECT    | 8   | 0               | parcial            | convenção                                                   |
| AE-DELI        | 4   | 4               | 4                  | convenção                                                   |
| CCT-ALT-RECT   | 4   | 0               | parcial            | convenção                                                   |
| AV-CES-VIG     | 2   | 0               | 2                  | aviso                                                       |
| PE-ALT         | 1   | 0               | 1                  | extensão                                                    |
| PCT-ALT        | 1   | 0               | 1                  | extensão                                                    |
| ACORDÃO        | 1   | 0               | 1                  | **ignorado**; corrigido em `main`                           |

**Consequência direta (2026-11-25).** Com o código de então, as 9 adesões e o acórdão não são
descarregados nem convertidos. É uma correção necessária antes de tudo o resto: acrescentar
`ADESÃO` à família adesão e criar uma família para decisões judiciais.

Outros factos relevantes:

1. `IDDocumento` é único (411 valores). É a melhor chave de documento.
2. `NomePDF` repete-se entre boletins (320 valores para 411 linhas), mas nunca dentro do
   mesmo boletim. A chave atual `ano/NBTE/NomePDF` continua válida; o nome de origem
   sozinho não serve para o MAXQDA.
3. `CAE` e `PagVersaoEscrita` estão vazias em todas as linhas. A CAE terá de vir de
   `SetoresAtividade`, preenchida em todas.
4. Nas PE e adesões, o `CodigoGEPDGERT` é o da convenção de base: confirmei-o nos 41 casos em
   que a convenção de base também está no índice de 2026, sem nenhuma divergência.
5. Dos 55 `ACT`, 45 são acordos coletivos de empregador público (o título começa por
   "Acordo coletivo de trabalho n.º N/2026 - Acordo coletivo de empregador público entre").
   Destes, 46 não têm `CodigoGEPDGERT`.

## 3. Tipologia proposta para o MAXQDA

Proponho cinco tipologias, cada uma com o seu XLSX e o seu grupo de documentos. O critério
é partilharem as mesmas variáveis.

| Tipologia (grupo e XLSX) | Tipos do índice                                          | N   | Tipo_conv (Listas) |
| ------------------------ | -------------------------------------------------------- | --- | ------------------ |
| A. Convenções            | CCT, CCT-ALT, AE, AE-ALT, ACT, ACT-ALT, \*-RECT, AE-DELI | 280 | CC, AE, AC, ACEP   |
| B. Adesões               | ADESÃO                                                   | 9   | ADESÃO             |
| C. Portarias             | PE, PE-ALT, PCT-ALT                                      | 110 | PE, PCT            |
| D. Avisos                | AVISO, AV-CES-VIG                                        | 11  | AVISO, AV          |
| E. Decisões judiciais    | ACORDÃO                                                  | 1   | ACÓRDÃO            |

**Interpretação.** A folha `Listas` inclui `Retificação` e `Deliberação` como valores de
`SubTipo_conv`. Por isso proponho que retificações e deliberações fiquem com as convenções,
e não numa tipologia própria.

### 3.1 Correspondência Tipo_conv

| Tipo no índice                                  | Tipo_conv proposto | Regra              |
| ----------------------------------------------- | ------------------ | ------------------ |
| CCT, CCT-ALT, CCT-ALT-RECT                      | CC                 | prefixo            |
| AE, AE-ALT, AE-ALT-RECT, AE-DELI                | AE                 | prefixo            |
| ACT, ACT-ALT com "empregador público" no título | ACEP               | título             |
| restantes ACT, ACT-ALT                          | AC                 | prefixo            |
| ADESÃO                                          | ADESÃO             | igual              |
| PE, PE-ALT                                      | PE                 | prefixo            |
| PCT-ALT                                         | PCT                | prefixo            |
| AVISO                                           | AVISO              | igual              |
| AV-CES-VIG                                      | AV                 | prefixo            |
| ACORDÃO                                         | ACÓRDÃO            | grafia de `Listas` |

**Pergunta 1.** O valor `ACC` de `Listas` não aparece no índice de 2026. A que tipo
corresponde?

### 3.2 Variáveis por tipologia

`S` aplica-se; `-` não se aplica (coluna omitida desse XLSX); `T` vem de tabela da equipa.

| Variável                                                     | A. Convenções | B. Adesões | C. Portarias  | D. Avisos | E. Judiciais |
| ------------------------------------------------------------ | ------------- | ---------- | ------------- | --------- | ------------ |
| Num_BTE, Data_pub, Ano_pub                                   | S             | S          | S             | S         | S            |
| IDDocumento, TipoSubTipoDoc                                  | S             | S          | S             | S         | S            |
| Natureza, SetorPublicoEmpresarial                            | S             | S          | S (da base)   | S         | -            |
| Tipo_conv, SubTipo_conv, SubTipo_conv_Reg                    | S             | S          | S             | S         | S            |
| Entidade_patronal_1, Entidade_sindical_1                     | S             | S          | S (do título) | S         | -            |
| CAE_sec, CAE_div, EtiquetaCAE_rev4                           | S             | S          | S             | S         | -            |
| Amb_Geografico                                               | T             | T          | T             | T         | -            |
| Paralelos_Binario, Paralelos_Grupo                           | T             | -          | -             | -         | -            |
| CodigoGEPDGERT (convenção de base)                           | S             | S          | S             | S         | S            |
| Doc_base (ID da convenção alterada, estendida ou retificada) | S             | S          | S             | S         | S            |
| Portaria (n.º e ano no DR)                                   | -             | -          | S             | -         | -            |

As colunas de 2026 que o MAXQDA exporta mas que não são variáveis (`Modificado por`,
`Segmentos codificados`, `Palavras`, etc.) ficam fora dos ficheiros de importação.

**Pergunta 2.** As variáveis de conteúdo da folha `MaxQDA_Variaveis` (`Num_trab_abrangidos`,
`Vigencia_conv`, `Eficacia`, `Prazo_denuncia`, `Renovacao_auto`, `Vigencia_tab_sal`,
`Sobrevigencia`) são preenchidas por leitura dos documentos no MAXQDA. Confirma que ficam
fora dos ficheiros gerados, para não apagar valores já introduzidos?

## 4. Extração do subtipo a partir do título

### 4.1 Regra (convenções, adesões, deliberações, retificações)

1. Remover o ponto final e os espaços do título.
2. Tomar o texto depois do último ` - ` (todos os títulos usam hífen com espaços).
3. Comparar, sem distinguir maiúsculas, com a tabela de sufixos. A tabela é a de
   `Correspondencias` (M:N), passada a ficheiro CSV editável pela equipa.
4. Sem correspondência: o subtipo fica vazio e o documento entra na folha de revisão.

| Sufixo no título                                | Títulos | SubTipo_conv                               | SubTipo_conv_Reg |
| ----------------------------------------------- | ------- | ------------------------------------------ | ---------------- |
| Alteração salarial e outras                     | 97      | Alt. salarial e outras                     | Revisão Parcial  |
| Revisão global                                  | 41      | Revisão Global                             | Revisão Global   |
| Alteração salarial e outras e texto consolidado | 26      | Alt. salarial e outras e texto consolidado | Revisão Parcial  |
| Alteração salarial e outra                      | 19      | Alt. salarial e outras                     | Revisão Parcial  |
| Retificação                                     | 12      | Retificação                                | **?**            |
| Alteração salarial e outras/texto consolidado   | 7       | Alt. salarial e outras / texto consolidado | Revisão Parcial  |
| Deliberação da comissão paritária               | 4       | Deliberação                                | **?**            |
| Alteração salarial e outra e texto consolidado  | 3       | Alt. salarial e outras e texto consolidado | Revisão Parcial  |
| Alteração salarial e outra/texto consolidado    | 3       | Alt. salarial e outras / texto consolidado | Revisão Parcial  |
| Alteração salarial/texto consolidado            | 2       | Alt. salarial / texto consolidado          | Revisão Parcial  |
| Alteração salarial                              | 2       | Alt. salarial                              | Revisão Parcial  |
| Alteração                                       | 2       | Alteração                                  | Revisão Parcial  |
| Alteração salarial e texto consolidado          | 1       | Alt. salarial e texto consolidado          | Revisão Parcial  |
| Alterações                                      | 1       | Alteração                                  | Revisão Parcial  |

Os subtipos com `e texto consolidado` e com `/texto consolidado` ficam distintos, como
pediu. Nota: nos títulos a barra aparece sem espaços (`outras/texto`); em `Listas` aparece
com espaços (`outras / texto`). A tabela trata essa diferença.

**Pergunta 3.** A tabela de `Correspondencias` junta o singular `outra` ao plural `outras`.
Confirma?

**Pergunta 4.** Que `SubTipo_conv_Reg` recebem as retificações e as deliberações? A
fórmula do Copilot deixa-as vazias. Proponho repetir o valor (`Retificação`, `Deliberação`),
para que possam ser filtradas.

### 4.2 Títulos sem marcador de subtipo (190 casos)

| Tipo                | N   | Situação                                            | Proposta                                                                     |
| ------------------- | --- | --------------------------------------------------- | ---------------------------------------------------------------------------- |
| CCT                 | 4   | o título termina na sigla sindical (`... - SICOS.`) | `1ª Convenção`, se `DocAlteradosPorEste` estiver vazio; senão revisão manual |
| AE                  | 8   | idem (`... - SITRA.`)                               | idem                                                                         |
| ACT                 | 48  | sobretudo ACEP; título termina no sindicato         | idem; **a validar**                                                          |
| ADESÃO              | 9   | o título termina na convenção a que adere           | subtipo não se aplica; `SubTipo_conv` vazio                                  |
| PE, PE-ALT, PCT-ALT | 110 | sem subtipo no título                               | ver 4.3                                                                      |
| AVISO               | 9   | subtipo no início do título                         | ver 4.4                                                                      |
| AV-CES-VIG          | 2   | "Aviso sobre a data da cessação da vigência"        | ver 4.4                                                                      |

**Pergunta 5.** Uma convenção sem sufixo e sem documento alterado é uma primeira
convenção? Nos ACEP, o BTE pode publicar acordos que já existiam no Diário da República.

### 4.3 Portarias

1. O número e o ano da portaria vêm de `DocumentosEmVigor`
   (`Portaria n.º 457/2025/1 - Diário da República n.º 245/2025, Série I de 2025-12-22`).
   A regra resolve 109 de 110.
2. A exceção é o documento 133/2026 (`PE-ALT`). Na verdade é um aviso de citação de
   contrainteressados sobre a portaria 384/2025, e não uma alteração de portaria.
3. O `SubTipo_conv` proposto: `PE` sem marcador fica vazio. Para `PE-ALT` e `PCT-ALT`
   proponho `Alteração`.

**Pergunta 6.** O que é `Instrum. parcelar e transitório` em `Listas`, e a que documentos
se aplica?

### 4.4 Avisos

| Início do título                                            | N   | SubTipo_conv proposto          |
| ----------------------------------------------------------- | --- | ------------------------------ |
| Aviso n.º N/2026 - Alteração ao ...                         | 5   | Aviso Alteração                |
| Aviso n.º N/2026 - Alteração e texto consolidado ao ...     | 3   | **?** (não existe em `Listas`) |
| Aviso n.º N/2026 - Deliberação da comissão paritária ao ... | 1   | Deliberação                    |
| Aviso sobre a data da cessação da vigência ... (AV-CES-VIG) | 2   | **?** (`Aviso Revogação`?)     |

**Pergunta 7.** Acrescento `Aviso Alteração e texto consolidado` a `Listas`? A cessação
de vigência corresponde a `Aviso Revogação` ou a um valor novo?

## 5. Nome do documento (RNC) por tipologia

Os exemplos usam siglas reais da lista global. `[?]` marca o que a lista não resolve.

| Tipologia      | ID       | Nome RNC proposto                                          | Observações                               |
| -------------- | -------- | ---------------------------------------------------------- | ----------------------------------------- |
| A. CCT-ALT     | 49/2026  | `2026_BTE_04_PRI_049_CCT-ALT_27101_AHETA-SITESE`           | âmbito por omissão                        |
| A. CCT         | 61/2026  | `2026_BTE_06_PRI_061_CCT_27208_CAP-SETAAB`                 | revisão global                            |
| A. AE-ALT      | 18/2026  | `2026_BTE_01_SPE_018_AE-ALT_44980_STCP-SMTP`               | SPE vem da lista                          |
| A. ACT         | 16/2026  | `2026_BTE_01_PRI_016_ACT_17203_BRISA-SETACCOP+12`          | 14 outorgantes                            |
| A. ACT (ACEP)  | 34/2026  | `2026_BTE_03_APU_034_ACT_0_JF-VILA-NOVA-DE-MILFONTES-STAL` | sem código IRCT; ver 5.2                  |
| A. AE-DELI     | 36/2026  | `2026_BTE_03_SPE_036_AE-DELI_47048_TAP-SITAVA+1`           |                                           |
| A. AE-ALT-RECT | 220/2026 | `2026_BTE_18_SPE_220_AE-ALT-RECT_47048_TAP-SITAVA+1`       | siglas herdadas da convenção retificada   |
| B. ADESÃO      | 38/2026  | `2026_BTE_03_AA_038_26262_APICCAPS-SIMA`                   | código da convenção de base               |
| C. PE          | 1/2026   | `2026_BTE_01_PE_001_0457-2025_27157_[?]-SETAAB`            | siglas do título; patronal não encontrada |
| C. PCT-ALT     | 335/2026 | `2026_BTE_28_PCT_335_0306-2026_30350_[?]`                  | sem outorgantes nem partes no título      |
| D. AVISO       | 39/2026  | `2026_BTE_04_AVISO_039_[?]_CM-FIGUEIRO-DOS-VINHOS-SINTAP`  | sem código IRCT                           |
| D. AV-CES-VIG  | 331/2026 | `2026_BTE_27_AV_331_25859_APAT-FETESE`                     | siglas do título                          |
| E. ACORDÃO     | 348/2026 | **?**                                                      | sem esquema definido                      |

### 5.1 Siglas: cobertura medida

1. Nos 286 documentos com outorgantes, a lista dá as duas siglas (patronal e sindical) em
   219 (77%). A correspondência usa três regras: nome completo igual, sigla no fim
   (`... - SETAAB`, `(STAS)`) e sigla no início (`STAL - Sindicato ...`).
2. Os 67 restantes têm sobretudo entidades sem sigla na lista: `Águas do Norte, SA`,
   `Banco de Portugal` e alguns municípios e freguesias.
3. Os 125 sem outorgantes (PE, retificações, avisos de cessação, acórdão) precisam de
   siglas herdadas da convenção de base, quando está no índice, ou tiradas do título.
4. Algumas siglas canónicas diferem do uso corrente. Por exemplo, o MAIS SINDICATO tem a
   sigla `SBSTMS` na lista. Para o nome isso não é problema, mas convém saber.

### 5.2 Âmbito PRI, SPE, APU: o ponto mais frágil

1. **Facto.** A coluna `ambito` da lista só tem `SPE`, em 232 entidades. Nunca tem `PRI`
   nem `APU`.
2. **Proposta.** Aplicar a seguinte ordem:
   a) `APU` se a entidade tem `lado = administração pública` ou o documento é ACEP;
   b) `SPE` se a lista o indica;
   c) `PRI` nos restantes empregadores, com indicação "por omissão" na folha de revisão.
3. **Risco.** A regra c) pode classificar como privadas empresas públicas que não estejam na
   lista com `SPE`. Como o nome é imutável depois da importação, um erro aqui obriga a
   renomear documentos já codificados.

**Pergunta 8 (respondida a 2026-11-26).** As convenções são privadas por omissão. `SPE` e
`APU` são os casos menos frequentes. É também a ordem do ADR-0019. Ver secção 10.2.

**Pergunta 9.** Nos ACEP sem `CodigoGEPDGERT`, a SPEC-0004 manda usar `0`. Prefere o número
do acordo publicado (`ACT n.º 53/2016`)?

### 5.3 SetorPublicoEmpresarial

A lista tem `ambito_subsetor` com `SEE` (106), `SEL` (103) e `SER` (23). Proponho:
`SEE` → `Central`, `SEL` → `Local`, `SER` → `Regional`. Em 2025 só havia `Central` e
`Local`. **Pergunta 10.** Confirma a correspondência e o valor novo `Regional`? A secção
10.3 mostra o que o ficheiro de 2025 confirma.

## 6. Limite de caracteres

1. **Nome do documento:** máximo de 63 caracteres. Com as siglas da lista, a mediana é 47 e
   só um caso ultrapassa: `BRISA` com `AUTO-ESTRADAS-ATLANTICO`. Encurta-se só a sigla, como
   na SPEC-0004.
2. **Valores de texto:** proponho o mesmo limite de 63. Os valores de vocabulário fechado
   (`Listas`) já cabem. As etiquetas CAE passam a ter uma forma curta fixa, numa tabela,
   em vez de cortes a meio de palavra como em 2025.
3. **Nomes de variáveis:** mantêm-se os de 2025, todos curtos.
4. Qualquer valor acima do limite vai para a folha de revisão, sem corte silencioso.

## 7. Avaliação do que foi feito com o Copilot

| Folha                | O que tem                                                              | Avaliação                                                                                                                                     |
| -------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `Correspondencias`   | sufixos do título → subtipo; ACT → AC                                  | aproveitável; passa a CSV                                                                                                                     |
| `Regras_Outorgantes` | regra "sindic", FNE, FE e FENPROF como sindicais, uma exceção          | substituída pelo campo `lado` da lista global, mais fiável                                                                                    |
| `Regras_Ambito`      | 2 documentos confirmados ("Portugal continental")                      | aproveitável como semente da tabela de âmbito geográfico                                                                                      |
| `Conversao_CAE4`     | 495 descrições → secção e divisão; 397 de 411 documentos com resultado | aproveitável **depois de revista**; as decisões "Descritor não classificante" (152) e "Só secção" (18) são do Copilot e precisam de validação |

## 8. Correções prévias na aplicação

1. ~~Reconhecer `ADESÃO` como adesão e `ACORDÃO` como decisão judicial.~~ Feito em `main`
   (versão 0.4.0rc3), com as famílias `adesao` e `acordao`.
2. Ler `DocAlteradosPorEste` com códigos múltiplos e com espaços espúrios
   (`ACT. 20250429.199/2025`), que ocorrem em 5 portarias e nos 2 avisos de cessação.
3. Portar do projeto original a nomeação RNC, com a lista global de siglas como fonte.

## 9. Resumo das perguntas

1. Significado de `ACC` (hipótese na secção 10.4).
2. Variáveis de conteúdo fora dos ficheiros gerados.
3. Singular `outra` agregado a `outras`.
4. `SubTipo_conv_Reg` de retificações e deliberações.
5. Convenção sem sufixo nem documento alterado = 1ª convenção.
6. Significado de `Instrum. parcelar e transitório`.
7. Subtipos dos avisos.
8. ~~`PRI` por omissão ou bloqueio.~~ Respondida: `PRI` por omissão.
9. Código IRCT dos ACEP.
10. `SEE`, `SEL`, `SER` → `Central`, `Local`, `Regional`.
11. Esquema de nome para o acórdão (não previsto na SPEC-0004).

## 10. Respostas e revisão das regras do RNC (2026-11-26)

### 10.1 Onde vivem as regras e as listas (facto)

Com a integração dos PR #4, #18, #19 e #20 (versão 0.4.0rc3), este repositório passou a ter:

1. `vocabularios/` com `tipos_documento.csv`, `siglas_organizacoes.csv`,
   `empregadores_ambito.csv`, `entidades_administracao_publica.csv` e
   `actos_negociacao.csv`, como no `crl-app-cct`;
2. `siglas.csv` na raiz, com cópia em `src/crl_markdown/vocabularios/siglas.csv`
   (3648 linhas, colunas `nome;sigla;codigo_dgert;lado;estado;origem_sigla;fonte;responsavel;data`);
3. `src/crl_markdown/vocabularios/tipologias_documentais.md` e `.json`, com as regras de
   ACEP, ACCE, deliberações e cessações de vigência;
4. a nomeação (`naming.py`), que lê `0_gestao/vocabularios/siglas.csv` e
   `0_gestao/vocabularios/empregadores_ambito.csv` da pasta de trabalho.

Os ADR que justificam estas regras (0017, 0018, 0019 e 0022) e a SPEC-0004 continuam só
no `crl-app-cct`.

O `docs/rnc/pastas/0_gestao.md` do projeto de origem fixa duas regras: os vocabulários
têm nome descritivo em minúsculas e sem data, e só há uma versão ativa de cada um. As
versões anteriores vão para `9_arquivo/0_gestao/` com data no nome.

**Consequência.** A lista de siglas, quando estiver pronta, entra em
`0_gestao/vocabularios/` com o nome `siglas.csv`, que é o que a aplicação lê.

### 10.2 Âmbito: PRI por omissão (decisão e regra existente)

A resposta de 2026-11-26 coincide com o ADR-0019. A ordem de classificação é esta:

1. vocabulário da equipa (`empregadores_ambito.csv`): decide, sem aviso;
2. lista do INE: propõe, sempre com aviso. Uma entidade com forma empresarial propõe `SPE`,
   nunca `APU`;
3. regra das formas jurídicas (`E.P.E.`, `E.M.`, `E.I.M.`);
4. omissão: `PRI`.

A ausência de uma entidade da lista não significa nada. A CP e a Carris não estão no S.13
e são `SPE`.

A coluna `ambito` da `lista_siglas_global` já incorpora os passos 2 e 3. Os fundamentos
registados são «INE S.13 2025: forma empresarial», «forma jurídica na denominação» e
«capital público maioritário». Por isso a regra da secção 5.2 fica assim:

1. `APU` nos acordos de empregador público (ACEP) e de carreira especial (ACCE), como em
   `tipologias_documentais.md`;
2. `SPE` quando a entidade empregadora tem `ambito = SPE` na lista ou está em
   `empregadores_ambito.csv`;
3. `PRI` nos restantes, sem bloqueio. A folha de revisão mostra os `SPE` de confiança
   `média`, que a lista manda confirmar no SIOE ou na DGTF.

**Interpretação.** Uma entidade com `lado = administração pública` que outorga uma
convenção que não é ACEP nem ACCE deve ir para revisão, e não para `APU` direto. O
ADR-0019 proíbe propostas automáticas de `APU` sem revisão.

### 10.3 O que o ficheiro de variáveis de 2025 confirma (facto)

1. Os 277 documentos têm `Natureza = Privada` e estão todos no grupo
   `Convencoes_Privadas_2025_TXT`.
2. Mesmo assim, 65 têm `SetorPublicoEmpresarial` preenchido: 36 `Local` e 29 `Central`.
   Em 2025, portanto, `Natureza` e `SetorPublicoEmpresarial` eram variáveis independentes.
   Uma empresa do SPE com contrato de trabalho privado era `Privada` com
   `SetorPublicoEmpresarial = Local`.
3. `Tipo_conv` só tem `AE` (135), `CC` (105) e `AC` (37). `ACC` e `ACEP` nunca aparecem.
4. `Amb_Geografico`, `Paralelos_Grupo` e `SetorPublicoEmpresarial` usam `0` para «não se
   aplica», o problema já descrito na análise prévia.

**Interpretação para 2026.** Proponho manter as duas variáveis. A primeira é `Natureza`,
com `Privada` ou `Pública`, derivada do âmbito. A segunda é `SetorPublicoEmpresarial`,
com `Central`, `Local` ou `Regional` para as entidades `SPE`. O quarto campo do nome RNC
(`PRI`, `SPE`, `APU`) fica coerente com as duas. A correspondência `SEE` → `Central`,
`SEL` → `Local` e `SER` → `Regional` é compatível com os valores de 2025. `Regional`
continua a ser um valor novo por confirmar.

### 10.4 Significado de `ACC` (hipótese de trabalho)

O código em `main` já trata o `ACCE` como acordo de carreira especial, família
`convencao`, âmbito `APU`. Na Lei Geral do Trabalho em Funções Públicas (Lei n.º 35/2014),
os acordos coletivos de trabalho dividem-se em acordos coletivos de carreira e acordos
coletivos de empregador público. Por isso `ACC` em `Listas` deve corresponder ao acordo
coletivo de carreira, o mesmo universo que o `ACCE`.

Esta leitura não está verificada: confirmar no artigo 13.º da LTFP. Se se confirmar,
proponho que `Tipo_conv` use um só valor para os dois códigos, `ACC` ou `ACCE`, à escolha
da equipa.

### 10.5 Listas de siglas em uso: risco a decidir

Há hoje três listas com siglas para as mesmas entidades:

| Lista                     | Linhas                        | Onde                                                           |
| ------------------------- | ----------------------------- | -------------------------------------------------------------- |
| `siglas_organizacoes.csv` | 2403 (só DGERT)               | `vocabularios/` deste repositório e do `crl-app-cct`           |
| `siglas.csv`              | 3648 (equipa, índice e DGERT) | raiz e `src/crl_markdown/vocabularios/`; é a que a nomeação lê |
| `lista_siglas_global`     | 6089 (DGERT, INE e CRL)       | versão de trabalho de 2026-11-24, ainda fora do Git            |

Comparei `siglas_organizacoes.csv` com a `lista_siglas_global` pelo código DGERT:

1. Todas as 2403 entradas antigas têm correspondência na lista nova.
2. A sigla é igual em 1629 entradas e diferente em 774. Por exemplo, `5.554.0` é `AANP` na
   lista antiga e `AGEPOR` na nova. `5.32.0` é `COMERCIALGUARDA` na antiga e `ACG` na nova.
3. As regras também diferem. A antiga aceita siglas de `recurso` em CamelCase e protege as
   siglas já atribuídas. A nova usa maiúsculas com hífen, um máximo de 12 caracteres (25
   para juntas, uniões de freguesias e câmaras) e reescreve as siglas fora do padrão.
4. As colunas da `lista_siglas_global` não são as que a nomeação lê. Para entrar como
   `siglas.csv` é preciso convertê-la (`sigla`, `nome`, `codigo_origem` e `lado` têm
   correspondência direta) ou adaptar o leitor.

O `0_gestao.md` avisa que «duas versões de um vocabulário em uso produzem duas nomeações
diferentes para o mesmo documento». Antes de a lista nova entrar em
`0_gestao/vocabularios/`, é preciso decidir uma de duas opções:

a) a lista nova substitui `siglas.csv` e `siglas_organizacoes.csv`, que passam para
   `9_arquivo/`;
b) a lista nova fica como fonte única, e `siglas.csv` passa a ser gerado a partir dela.

**Decisão de 2026-11-26: opção b).** A `lista_siglas_global` passa a ser a fonte única. O
`siglas.csv` é gerado por `scripts/gerar_siglas_da_lista_global.py` (ver
`vocabularios/README.md`). No índice de 2026, os documentos com outorgantes cujas duas
siglas escolhidas se resolvem sem aviso passam de 122 para 244 em 286.

**Conflitos da lista (decisão de 2026-11-26).** Nomes iguais em fontes diferentes ficam com
a sigla da DGERT, depois do INE, por fim do CRL (12 linhas). Freguesias cujos nomes só
diferem num acento ou num espaço coexistem, confirmadas na CAOP 2024.1 (Lousa e Lousã,
Mosteiro e Mosteirô, Paçó e Paçô, Tabua e Tábua, Travassos e Travassós). Ficam por
resolver 12 nomes com duas siglas na mesma fonte e a colisão `JF-AGUALONGA` /
`JF-AGUA-LONGA`, que a nomeação lê como `JFAGUALONGA`.

**Conflitos resolvidos (decisão de 2026-11-27).** As notas da equipa no relatório de
conflitos foram aplicadas na lista, com duas regras gerais:

1. no mesmo nome com duas siglas, a entidade ativa fica e a extinta sai do `siglas.csv`;
   uma entidade marcada `Desativada` na lista também sai (por exemplo, `SGP` dá lugar a
   `SG-PRESIDENC`). Quando todas as entidades com esse nome estão extintas, saem todas;
2. freguesias com nomes muito semelhantes levam o distrito na sigla, por exemplo
   `JF-AGUALONGA-VIANA-DO-CASTELO` e `JF-AGUA-LONGA-PORTO`. Travassos e Travassós ficam
   ambas no distrito de Braga, por isso levam o concelho (`JF-TRAVASSOS-POVOA-DE-LANHOSO`
   e `JF-TRAVASSOS-FAFE`).

Para caberem estas siglas, o limite da sigla na nomeação passou de 20 para 25
caracteres, o mesmo que a lista já usa para JF, UF e CM. A sigla inventada a partir do
nome, quando o vocabulário não tem nenhuma, continua limitada a 20. O limite de 63
caracteres do nome do documento não muda.

A `Freguesia de Mosteiro` tem três correspondências na CAOP (Vieira do Minho, Oleiros e
Lajes das Flores) e uma só linha na lista do INE. Entram as três, com o concelho no nome
e o distrito na sigla (`JF-MOSTEIRO-BRAGA`, `JF-MOSTEIRO-CASTELO-BRANCO`,
`JF-MOSTEIRO-FLORES`). Um documento que só diga «Freguesia de Mosteiro» recebe um aviso
para confirmar qual é.

Em qualquer dos casos, as siglas dos nomes já atribuídos ao corpus até 2025 não mudam
(ADR-0021). Para o corpus de 2026, a mudança tem de acontecer antes de começar a
codificação no MAXQDA (ADR-0022, transição).

**Estado da lista nova (facto).** A folha `pendentes_crl` ainda tem rótulos CRL sem
entidade atribuída, por exemplo `AIM`, com três candidatas. A coluna `revisao` tem 175
linhas com pendentes. A lista ainda não está pronta para ser o vocabulário ativo.

### 10.6 Próximos passos

1. ~~Decidir entre as opções a) e b) da secção 10.5.~~ Opção b).
2. ~~Converter a `lista_siglas_global` para o formato de `siglas.csv`.~~ Feito, com testes.
3. Trazer para este repositório os ADR 0017, 0018, 0019 e 0022 e a SPEC-0004, que
   justificam as regras já presentes.
4. Responder às perguntas 1 a 7 e 9 a 11 da secção 9.
5. Implementar o gerador do XLSX de variáveis por tipologia.
