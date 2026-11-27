# Variáveis de documento para o MAXQDA: análise prévia e exemplos para validação

Estado: proposta para validação, sem implementação. Data: 2026-11-24.
As decisões de 2026-11-25 e a tipologia com o índice real estão em
[tipologia-e-exemplos.md](tipologia-e-exemplos.md), que prevalece em caso de divergência.

## 1. Objetivo e contexto

A aplicação `crl-pdf-markdown` já recolhe os PDF do BTE a partir dos índices da DGERT
(`collect`) e converte-os em Markdown (`convert`). Falta um terceiro produto: um ficheiro
XLSX com as variáveis de documento, no formato que o MAXQDA aceita em
**Variáveis → Importar variáveis de documento**, semelhante ao ficheiro de referência de
2025 (`VarDoc_master`, 277 documentos, 18 colunas).

Este documento serve para validar as soluções antes de escrever código. Distingue três
níveis de afirmação:

1. **Facto**: verificado no código, nos testes ou no ficheiro de 2025.
2. **Interpretação**: leitura minha dos factos, que pode estar errada.
3. **Hipótese de trabalho**: proposta a confirmar com a equipa ou com um teste no MAXQDA.

Fontes analisadas: `variaveis_documento_maxqda_2025.xlsx`, o resumo das conversas com o
Copilot, o código de recolha deste repositório (`src/crl_markdown/recolha.py`,
`pipeline.py`) e o projeto original `crl-app-cct` (nomeação RNC, siglas, âmbito,
leitor de variáveis do MAXQDA, ADR-0022 e SPEC-0004).

## 2. O que o ficheiro de 2025 mostra

### 2.1 Estrutura (facto)

| Coluna                  | Tipo de valor | Valores observados                                                                                                                |
| ----------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Grupo do documento      | texto         | um só: `Convencoes_Privadas_2025_TXT`                                                                                             |
| Nome do documento       | texto         | `25_PR_001_BTE_01_AHP_SITESE_TXT`, até 60 caracteres                                                                              |
| Num_BTE                 | inteiro       | 1 a 48                                                                                                                            |
| Data_pub                | texto         | `08/01/2025 00:00:00` (texto, não data)                                                                                           |
| Ano_pub                 | inteiro       | 2025                                                                                                                              |
| Natureza                | texto         | só `Privada`                                                                                                                      |
| SetorPublicoEmpresarial | misto         | `0` (212), `Local` (36), `Central` (29)                                                                                           |
| Tipo_conv               | texto         | `AE` (135), `CC` (105), `AC` (37)                                                                                                 |
| SubTipo_conv            | texto         | 8 valores, ver 2.2                                                                                                                |
| SubTipo_conv_Reg        | texto         | `Revisão Parcial` (206), `Revisão Global` (52), `1ª Convenção` (19)                                                               |
| CAE_sec                 | texto         | 17 secções                                                                                                                        |
| CAE_div                 | inteiro       | `0` em 223 linhas; só preenchida na secção C                                                                                      |
| EtiquetaCAE_rev4        | texto         | cortada aos 63 caracteres                                                                                                         |
| Entidade_patronal_1     | texto         | 199 valores, forma livre                                                                                                          |
| Entidade_sindical_1     | texto         | 70 valores                                                                                                                        |
| Amb_Geografico          | misto         | `0` (98), `Nacional` (102), `Intermunicipal`, `Distrito`, `Município`, `Nacional e Outros`, `Continente`, `Regional`, `Freguesia` |
| Paralelos_Binario       | inteiro       | `0` (204), `1` (73)                                                                                                               |
| Paralelos_Grupo         | misto         | `0` ou `Paralelo_CARRIS_1`, `Paralelo_ANILACT_1`, etc.                                                                            |

### 2.2 Subtipos e regra de agregação (facto)

| SubTipo_conv                               | Ocorrências | SubTipo_conv_Reg |
| ------------------------------------------ | ----------- | ---------------- |
| Alt. salarial e outras                     | 130         | Revisão Parcial  |
| Revisão Global                             | 52          | Revisão Global   |
| Alt. salarial e outras e texto consolidado | 40          | Revisão Parcial  |
| Alt. salarial e outras / texto consolidado | 21          | Revisão Parcial  |
| 1ª Convenção                               | 19          | 1ª Convenção     |
| Alteração                                  | 9           | Revisão Parcial  |
| Alt. salarial                              | 5           | Revisão Parcial  |
| Alt. salarial e texto consolidado          | 1           | Revisão Parcial  |

A fórmula proposta pelo Copilot para `SubTipo_conv_Reg` reproduz esta regra.

### 2.3 Problemas de qualidade no ficheiro de 2025

1. **Facto.** O valor `0` representa "sem informação" ou "não se aplica" em colunas de
   texto (`Amb_Geografico`, `SetorPublicoEmpresarial`, `Paralelos_Grupo`) e numéricas
   (`CAE_div`). **Interpretação:** no MAXQDA, `0` é um valor como outro qualquer; aparece
   nas tabelas de frequência e nos filtros como uma categoria real.
2. **Facto.** `Natureza` é `Privada` em todos os documentos, incluindo 65 de setor
   público empresarial. A variável não discrimina nada em 2025.
3. **Facto.** Há duas grafias para o mesmo subtipo: `... e texto consolidado` e
   `... / texto consolidado`.
4. **Facto.** O nome `25_PR_125_BTE_21_IPOCoimbra _SIM_TXT` tem um espaço.
5. **Facto.** `Data_pub` é texto. **Interpretação:** impede filtros por intervalo de datas
   no MAXQDA.
6. **Facto.** `EtiquetaCAE_rev4` está cortada aos 63 caracteres
   (`J - Atividades de edição, difusão e produção e distribuição de`). **Hipótese:** é o
   limite de comprimento das variáveis de texto da versão do MAXQDA usada; confirmar.
7. **Facto.** As siglas das entidades não seguem uma regra única: `AHP - Ass. Hotel. Port.`,
   `NAV- PORTUGAL`, `ULSAS-saude`, `Várias Instituições de Crédito`.

## 3. Análise crítica de cada passo

### Passo 1. Do site do BTE ao índice da DGERT

1. **Facto.** A aplicação depende de índices XLSX fornecidos pela equipa. Reconhece dois
   dialetos de cabeçalho (rótulos com dois pontos e nomes técnicos como `IDDocumento`,
   `TipoSubTipoDoc`, `CodigoGEPDGERT`).
2. **Facto.** A família documental é derivada do prefixo do tipo: `CCT`, `ACT`, `AE`, `ACEP`,
   `ACTV`, `DA` são convenção; `PE`, `PCT`, `PRT` extensão; `AA` adesão; `AVISO`, `AV`
   aviso. Qualquer outro tipo fica `ignorado` e não é descarregado.
3. **Risco.** O Copilot contou 16 tipos no índice de 2026. Não sei quais são. Se incluírem
   deliberações de comissões paritárias, regulamentos de condições mínimas ou outros, esses
   documentos não chegam ao Markdown nem às variáveis. **Preciso do índice real de 2026**
   para listar os 16 tipos e decidir cada um.
4. **Risco.** O subtipo descritivo (`Alt. salarial e outras`) não existe em nenhuma coluna
   lida pela aplicação. No teste de 2 de outubro foi lido do título, porque a segunda coluna
   `TIPO DE DOCUMENTO:` vinha vazia. O Copilot usou `TEXTODEPOIS(AM2#;"-")`, o que sugere
   que no livro de 2026 existe uma coluna com `CCT - Alt. salarial e outras`. Tenho de ver
   qual.
5. **Facto.** As colunas `VIDE DOCUMENTO(S) EM VIGOR:` e `LINK VIDE DOCUMENTO(S) EM VIGOR:`
   não correspondem a nenhum alias e são ignoradas. Não afeta as variáveis de 2025, mas
   afeta uma eventual variável de ligação ao documento em vigor.

### Passo 2. Do índice ao catálogo `registo_bte.jsonl`

1. **Facto.** O catálogo guarda ano, número BTE, ID DGERT, tipo bruto (`AE-ALT-RECT`),
   família, código IRCT, CAE, título, outorgantes, setores, URL, ficheiro, datas e
   alterações. A chave é `ano/num_bte/nome_pdf`, por exemplo `2026/31/00260057`.
2. **Facto.** Não guarda subtipo, âmbito (PRI, SPE, APU), siglas nem nome RNC. Essa lógica
   existe no projeto original (`nomeacao.py`, `ambito.py`, `siglas.py`) mas não foi portada.
3. **Interpretação.** O catálogo é a fonte certa para as variáveis que vêm do índice. As
   restantes (âmbito geográfico, CAE validada, paralelos, siglas confirmadas) precisam de
   tabelas mantidas pela equipa, lidas em cada execução e nunca sobrescritas.

### Passo 3. Do catálogo ao Markdown

1. **Facto.** O Markdown tem o nome de origem do PDF: `results/bte/2026/31/00260057.md`.
2. **Risco elevado.** No MAXQDA, o nome do documento importado é o nome do ficheiro sem
   extensão. `00260057` não é único: o mesmo intervalo de páginas pode repetir-se noutro
   boletim ou noutro ano. Importar estes ficheiros diretamente pode produzir nomes
   repetidos, e as variáveis seriam atribuídas ao documento errado ou a nenhum.
3. **Conclusão.** O nome usado no MAXQDA tem de ser decidido **antes** de gerar o XLSX, e o
   mesmo passo da aplicação tem de produzir o nome do ficheiro Markdown e a linha do XLSX.
   Gerar os dois por caminhos diferentes (Python para o Markdown, fórmulas para o XLSX) é a
   principal fonte de erro.

### Passo 4. Importação no MAXQDA

1. **Facto.** O teste de 2 de outubro, com QDPX, reconheceu as variáveis mas não atribuiu
   os valores. A causa técnica não foi apurada.
2. **Interpretação.** A importação de variáveis por XLSX é a via nativa do MAXQDA e evita a
   dependência da representação de casos do QDPX. É uma alternativa sólida.
3. **Hipótese a testar.** O MAXQDA identifica cada documento pela combinação
   **Grupo do documento + Nome do documento**. Se o grupo do XLSX não for exatamente o grupo
   onde o documento foi importado, a linha é ignorada. Isto obriga a fixar também a regra
   dos grupos.
4. **Hipótese a testar.** As variáveis novas são criadas como texto. Para que `Num_BTE`,
   `Ano_pub` e `Data_pub` funcionem como número e data, podem ter de ser criadas
   previamente no projeto com o tipo certo.
5. **Hipótese a testar.** Uma célula vazia deixa a variável sem valor, o que é preferível ao
   `0` de 2025. Confirmar que o MAXQDA não rejeita a linha.

### Passo 5. Uso das variáveis na análise

1. **Interpretação.** As variáveis servem para ativar documentos por critérios, comparar
   grupos e cruzar códigos. Isso exige vocabulários fechados e estáveis entre anos. Um
   mesmo conceito com duas grafias divide a contagem.
2. **Risco.** Valores múltiplos numa só célula (o Copilot propôs CAE separadas por `;`)
   criam combinações únicas que não se agrupam. Recomendo uma CAE principal por documento
   e, se necessário, uma variável à parte para documentos multissetoriais.
3. **Risco.** Retificações e avisos importados como documentos ficam com variáveis vazias
   se as regras forem as das convenções. Devem herdar ou referir o documento a que dizem
   respeito.

## 4. Decisões que preciso que valide

### 4.1 Nome do documento

| Opção                                                         | Exemplo                                          | Origem dos campos        | Vantagens                              | Riscos                                                                     |
| ------------------------------------------------------------- | ------------------------------------------------ | ------------------------ | -------------------------------------- | -------------------------------------------------------------------------- |
| A. Nome RNC completo (ADR-0022)                               | `2026_BTE_31_PRI_377_CCT-ALT_27251_ACRAL-CESP+3` | índice + âmbito + siglas | segue a norma aprovada; legível        | âmbito e siglas não estão a 100%; o nome é imutável depois da importação   |
| B. Nome RNC sem âmbito nem siglas                             | `2026_BTE_31_377_CCT-ALT_27251`                  | só índice                | determinístico, único, sem heurísticas | diverge da norma; menos legível na lista do MAXQDA                         |
| C. Ler os nomes de uma pasta já nomeada (proposta do Copilot) | o que estiver na pasta                           | ficheiros existentes     | aproveita trabalho já feito            | depende de uma renomeação feita fora da aplicação; pode haver divergências |
| D. Esquema de 2025                                            | `26_PR_003_BTE_31_ACRAL_CESP`                    | índice + siglas          | continuidade com 2025                  | ADR-0021 determina o esquema RNC a partir de 2026                          |

**Recomendação:** opção A com um bloqueio. Para cada documento, a aplicação propõe âmbito e
siglas; um documento só recebe nome final quando âmbito e siglas estiverem confirmados numa
tabela da equipa. Os restantes ficam `por_confirmar` numa folha de revisão e não entram no
XLSX nem na pasta de importação. Critério: o nome não pode mudar depois da codificação.
Se a confirmação manual for demasiado pesada, a opção B é a alternativa segura.

### 4.2 Grupo do documento

Proposta: um grupo por ano e família, por exemplo `Convencoes_2026`, `Extensoes_2026`,
`Adesoes_2026`. A aplicação colocaria os Markdown em pastas com estes nomes, para que a
importação por pasta produza os mesmos grupos. **Pergunta:** em 2025 havia só um grupo e o
sufixo `_TXT`. O sufixo foi intencional ou resultou da forma de importação?

### 4.3 Valores em falta

Proposta: célula vazia para "sem informação" e um valor explícito (`Não aplicável`) só
quando a variável não se aplica ao tipo de documento. Abandonar o `0` em colunas de texto.
**Atenção:** isto quebra a comparabilidade direta com 2025, salvo se o ficheiro de 2025 for
também corrigido.

### 4.4 Variáveis novas

Proposta de colunas adicionais, todas vindas do índice: `ID_DGERT` (`377/2026`),
`Cod_IRCT`, `Tipo_BTE` (código bruto, por exemplo `AE-ALT-RECT`), `Familia`,
`Texto_consolidado` (0 ou 1) e `Doc_referido` (ID do documento retificado, estendido ou
aderido). Permitem distinguir casos que `SubTipo_conv_Reg` agrega.

## 5. Exemplos por tipo de documento

Os exemplos de 2026 vêm do BTE 31/2026 usado nos testes. Os campos que dependem de
tabelas da equipa estão marcados com `[tabela]`; os que ainda não sei obter, com `[?]`.

### 5.1 Convenções: primeira convenção e revisão global

| Campo                              | CCT 377/2026                                      | AE 382/2026                                                                                  |
| ---------------------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Tipo no índice                     | `CCT`                                             | `AE`                                                                                         |
| Título                             | Contrato coletivo entre a ... ACRAL e o CESP ...  | Acordo de empresa entre a Empresa Metropolitana de Estacionamento da Maia, EM e o ... SINTAP |
| Nome (opção A)                     | `2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+3`      | `2026_BTE_31_SPE_382_AE_47252_EmpresaMetropolitana-SINTAP`                                   |
| Nome (opção B)                     | `2026_BTE_31_377_CCT_27251`                       | `2026_BTE_31_382_AE_47252`                                                                   |
| Tipo_conv                          | `CC`                                              | `AE`                                                                                         |
| SubTipo_conv                       | `[?]` (revisão global, segundo o corpus de teste) | `[?]`                                                                                        |
| SubTipo_conv_Reg                   | `Revisão Global`                                  | `[?]`                                                                                        |
| Natureza / SetorPublicoEmpresarial | `Privada` / vazio                                 | `[tabela]` / `Local`                                                                         |
| Entidade_patronal_1                | `ACRAL`                                           | `[tabela]` (sigla derivada `EmpresaMetropolitana`, a confirmar)                              |
| Entidade_sindical_1                | `CESP`                                            | `SINTAP`                                                                                     |
| Amb_Geografico                     | `[tabela]`                                        | `[tabela]`                                                                                   |

**Ponto de atenção:** em 382, a sigla patronal foi derivada do nome por regra e não é
canónica. É exatamente o caso que deve ficar `por_confirmar`.

### 5.2 Convenções: revisão parcial

| Campo                    | CCT-ALT 378/2026                                 | CCT-ALT 379/2026                                | AE-ALT 385/2026                                     |
| ------------------------ | ------------------------------------------------ | ----------------------------------------------- | --------------------------------------------------- |
| Outorgantes              | CNIS; FNSTFPS                                    | AEVP; FESAHT                                    | AP Solutions GMBH; STAS                             |
| Nome (opção A)           | `2026_BTE_31_PRI_378_CCT-ALT_26760_CNIS-FNSTFPS` | `2026_BTE_31_PRI_379_CCT-ALT_26651_AEVP-FESAHT` | `2026_BTE_31_PRI_385_AE-ALT_47140_APSolutions-STAS` |
| SubTipo_conv_Reg         | `Revisão Parcial`                                | `Revisão Parcial`                               | `Revisão Parcial`                                   |
| Texto_consolidado (nova) | `[?]`                                            | `[?]`                                           | `[?]`                                               |

**Ponto de atenção:** a CNIS é patronal, a FNSTFPS é sindical. A regra "contém sindic"
classifica-as bem, mas falha em sindicatos que atuam como empregadores, exceção que o
Copilot já registou. Em 2025, `AP Solutions GMBH` aparece por extenso: a sigla
`APSolutions` seria nova.

### 5.3 Retificações

| Campo                 | AE-ALT-RECT 387/2026                                                        |
| --------------------- | --------------------------------------------------------------------------- |
| Título                | Acordo de empresa entre a CARRISTUR ... e a Associação Sindical ... (ASPTC) |
| Outorgantes no índice | vazio                                                                       |
| Nome (opção A)        | `2026_BTE_31_SPE_387_AE-ALT-RECT_47109_CARRISTUR-ASPTC`                     |
| SubTipo_conv_Reg      | vazio pela regra do Copilot                                                 |

**Pergunta:** as retificações entram no MAXQDA como documentos próprios? Se sim, proponho
`SubTipo_conv_Reg = Retificação` e `Doc_referido` com o ID do documento retificado. As
entidades vêm do título, porque a coluna de outorgantes está vazia.

### 5.4 Portarias de extensão (exemplo da SPEC-0004, não do índice real)

| Campo              | PE                                                                 |
| ------------------ | ------------------------------------------------------------------ |
| Nome (opção A)     | `2026_BTE_01_PE_012_0452-2025_27251_ACRAL-CESP`                    |
| Campos necessários | número e ano da portaria no DR; código IRCT da convenção estendida |
| Variáveis de 2025  | não existiam: o ficheiro de 2025 só tem convenções                 |

**Perguntas:** as PE entram nesta análise? Que variáveis fazem sentido: as da convenção
estendida (CAE, entidades, âmbito) ou só identificação e ligação?

### 5.5 Acordos de adesão (exemplo da SPEC-0004)

| Campo          | AA                                   |
| -------------- | ------------------------------------ |
| Nome (opção A) | `2026_BTE_12_AA_412_27251_ABC-CESP`  |
| Ligação        | código IRCT da convenção a que adere |

### 5.6 Avisos

**Facto.** No projeto original os avisos não têm ficheiro, só linha no catálogo. Esta
aplicação descarrega-os por omissão (família `aviso`). **Pergunta:** os avisos vão para o
MAXQDA? Se não, proponho excluí-los do XLSX.

### 5.7 Outros tipos

O Copilot encontrou 16 tipos no índice de 2026. Sem o índice real não consigo listá-los nem
dar exemplos de deliberações ou de outros casos que hoje ficam `ignorado`.

## 6. Variáveis que o índice não fornece

| Variável                                 | Situação                                                                                        | Proposta                                                                                                                              |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Amb_Geografico                           | não está no índice; o Copilot confirmou 2 em 411                                                | tabela da equipa por código IRCT; sem entrada, célula vazia                                                                           |
| CAE_sec, CAE_div, EtiquetaCAE_rev4       | o índice tem `SECTOR(ES) DE ACTIVIDADE` em texto livre, misturado com matérias (`REMUNERAÇÕES`) | tabela de correspondência descrição → CAE Rev. 4, validada pela equipa; a aplicação só aplica o que estiver na tabela e lista o resto |
| Paralelos_Binario, Paralelos_Grupo       | decisão analítica                                                                               | a aplicação pode **sugerir** candidatos (mesma entidade patronal e mesmo boletim), sem preencher                                      |
| Entidade_patronal_1, Entidade_sindical_1 | o índice tem nomes completos                                                                    | sigla de uma tabela da equipa; sem entrada, sigla derivada marcada para revisão                                                       |
| SetorPublicoEmpresarial, Natureza        | o projeto original classifica PRI, SPE e APU com vocabulário, lista do INE e regras             | aplicar essa lógica; os valores `Local` e `Central` exigem uma regra nova ou tabela                                                   |

**Nota sobre as conversas com o Copilot.** As etiquetas "Rever" e "Não usar" na conversão
CAE foram criadas pelo próprio Copilot e apresentadas como limitações dos dados. Isto mostra
o risco de regras implícitas em fórmulas. Proponho que todas as tabelas de correspondência
sejam ficheiros CSV versionados, com colunas de fonte, data e responsável, como já acontece
em `vocabularios/empregadores_ambito.csv` no projeto original.

## 7. Arquitetura proposta (para discussão, não implementada)

1. Novo comando `crl_markdown variaveis`, que lê o catálogo e as tabelas da equipa.
2. Produz um XLSX com três folhas:
   a) `VarDoc` com as colunas para importar no MAXQDA, sem fórmulas;
   b) `Revisao` com os documentos e células por confirmar e o motivo;
   c) `Proveniencia` com a origem de cada valor (índice, tabela, regra).
3. O mesmo comando cria ou atualiza a pasta de importação com os Markdown renomeados,
   garantindo que nome do ficheiro e linha do XLSX coincidem.
4. Os nomes atribuídos ficam registados no catálogo e nunca são recalculados.
5. Testes automáticos com os exemplos da secção 5 e com o ficheiro de 2025 como referência
   de formato.

**Porquê Python e não fórmulas.** A transformação é recorrente, mas as regras (siglas,
âmbito, CAE) evoluem. Num livro com fórmulas, cada alteração pode afetar centenas de linhas
sem aviso. Em código, cada regra tem teste e cada valor tem origem rastreável. A equipa
continua a trabalhar em Excel nas tabelas de correspondência, que é onde o conhecimento
está.

## 8. Teste piloto antes da implementação completa

Recomendo um teste com 3 documentos (uma revisão global, uma revisão parcial e uma
retificação) para confirmar no MAXQDA:

1. se o grupo do documento tem de coincidir;
2. que tipos de variável são criados na importação;
3. como são tratadas as células vazias e as datas;
4. se há limite de 63 caracteres nos valores de texto;
5. a versão do MAXQDA usada, que o teste de 2 de outubro não registou.

## 9. O que preciso para avançar

1. O índice real de 2026 (ou o livro `2026_RNC_vardoc_2026` do Copilot), para listar os 16
   tipos e localizar o subtipo descritivo.
2. A escolha do nome do documento (4.1) e dos grupos (4.2).
3. A decisão sobre que famílias entram no MAXQDA: retificações, PE, AA, avisos.
4. As tabelas já existentes: siglas, âmbito geográfico, CAE e a folha `Listas` com os
   valores aceites.
5. A versão do MAXQDA.

## 10. Pontos-chave

1. O ponto crítico é a correspondência exata entre o nome do documento no MAXQDA e o nome
   no XLSX. Ambos têm de sair do mesmo passo da aplicação.
2. Metade das variáveis vem do índice e pode ser automática; a outra metade depende de
   tabelas da equipa e deve ficar vazia até ser confirmada.
3. O ficheiro de 2025 tem incoerências (zeros como ausência, grafias duplas, datas em texto)
   que convém não reproduzir.
4. As PE, AA, avisos e retificações não têm modelo em 2025; precisam de decisão.
5. Um teste piloto com 3 documentos resolve as dúvidas sobre o comportamento do MAXQDA.
