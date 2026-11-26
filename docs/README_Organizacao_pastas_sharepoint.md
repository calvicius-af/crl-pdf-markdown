# RNC: organização e nomenclatura dos ficheiros

Relatório da Negociação Coletiva · Centro de Relações Laborais · Versão 4.0 · 17 de setembro de 2026

Substitui `README.Estrutura_RNC_2027.docx` (v2.1), `README_Estrutura_RNC_2026.md` (v1) e as secções 2 e 3 do `SOP_Gestao_Documental_RNC_2026.docx` (v1.0). O registo de alterações está no final; a fundamentação de cada decisão está nos ADR referidos ao longo do texto.

## Três regras

1. As pastas seguem a fase do trabalho, nunca o tema. Um ficheiro está em `1_fontes/` porque acabou de chegar, não porque é sobre teletrabalho.
2. O nome do ficheiro não muda depois de atribuído. É atribuído uma vez, pela aplicação, à entrada. Mudam a extensão e a pasta.
3. O catálogo manda. Se a pasta e o catálogo divergirem, o catálogo está certo e a pasta está por arrumar.

Exemplo de um nome real, gerado a partir do BTE 31 de 2026:

```text
2026_PRI_377_CCT_27251_BTE_31_ACRAL-CESP-STRUP+2.pdf
 │    │    │   │    │      │     └── siglas das partes (3 primeiras, +2 = há mais duas)
 │    │    │   │    │      └── número do boletim em que saiu
 │    │    │   │    └── código IRCT, o mesmo em todas as revisões desta convenção
 │    │    │   └── tipo de documento, tal como vem do BTE
 │    │    └── número sequencial do ano (o «377/2026» do índice)
 │    └── âmbito: PRI, SPE ou APU. Diz de imediato se é processável.
 └── ano de publicação
```

---

## 1. Âmbito

Este documento define onde fica cada ficheiro do RNC e como se chama, para que qualquer pessoa da equipa, ou uma perita externa que chegue a meio do ciclo, encontre o que precisa sem perguntar a ninguém. Aplica-se a todas as fases: recolha, processamento, codificação, redação e coordenação.

Não substitui o manual do MAXQDA, o livro de códigos nem o roteiro do relatório, que vivem em `0_gestao/`. Para a operação da aplicação, ver o [guia de operação](../operacao/guia-operacao.md).

**Termos usados.** *IRCT*: instrumento de regulamentação coletiva de trabalho, designação genérica para convenções, portarias e acordos de adesão. *BTE*: Boletim do Trabalho e Emprego, onde são publicados. *Índice do BTE*: ficheiro XLSX que a DGERT distribui por número do boletim, com uma linha por documento publicado. *Catálogo*: CSV mantido pela equipa, com uma linha por documento recolhido. *QDPX*: formato REFI-QDA de troca de projetos entre programas de análise qualitativa, usado para entregar o trabalho ao MAXQDA.

---

## 2. Árvore de pastas

```text
RNC_Dados_2026/
├── README.md                    este ficheiro
├── 0_gestao/
│   ├── roteiro/                 índice do relatório, versão vigente e anteriores
│   ├── livro_codigos/           árvore de códigos MAXQDA e crosswalk de temas
│   ├── catalogo/                catalogo_irct_2026.csv, a fonte de verdade
│   ├── vocabularios/            listas controladas (ver 7)
│   ├── atas/                    reuniões e decisões de codificação
│   └── procedimentos/           este README, SOP, guias
├── 1_fontes/                    tudo o que entra de fora. Imutável.
│   ├── indices_bte/             os XLSX de índice
│   ├── bte_completo/            boletins inteiros em PDF
│   ├── irct/
│   │   ├── convencoes/          PRI/ SPE/ APU/   o pipeline lê daqui
│   │   ├── portarias_extensao/
│   │   └── acordos_adesao/
│   └── externas/                DGERT, DGAEP, INE, CITE, Eurofound, RAA, RAM
├── 2_processamento/             saídas automáticas da aplicação
│   ├── texto/                   ver a nota em 3.1
│   ├── precodificado/           ver a nota em 3.1
│   └── qdpx/                    pacotes QDPX prontos a importar
├── 3_analise/                   MAXQDA
│   ├── master/                  um único .mqda ativo
│   ├── mqex/                    exports individuais por integrar
│   ├── comparacoes/             diacronia entre versões de uma convenção
│   └── logs_integracao/         registo de cada integração no master
├── 4_temas/                     entregas às peritas (ver 5)
├── 5_redacao/                   capítulos em elaboração
├── 6_relatorio/                 relatório consolidado
├── 7_divulgacao/                apresentação, imprensa, fotografias
└── 9_arquivo/                   versões superadas de tudo o resto
```

A pasta-raiz chama-se `RNC_Dados_AAAA`, em que AAAA é o ano a que os dados dizem respeito e não o ano de publicação. O relatório publicado em 2027 sobre dados de 2026 vive em `RNC_Dados_2026/`.

As pastas que concentram o risco são quatro: `0_gestao/catalogo/`, `1_fontes/irct/`, `3_analise/master/` e `4_temas/`.

---

## 3. Ciclo de vida de um documento

Um IRCT entra uma vez e atravessa oito fases. O nome base mantém-se; mudam a extensão e a pasta.

| # | Fase | Quem | Entra | Sai | Fica em |
|---|---|---|---|---|---|
| 1 | Recolha | Técnico de recolha | índice XLSX do BTE | 1 PDF por IRCT, renomeado, e linha no catálogo | `1_fontes/irct/{FAMILIA}/` |
| 2 | Extração | Aplicação | PDF de `convencoes/` | texto com estrutura preservada | em memória (ver 3.1) |
| 3 | Pré-codificação | Aplicação | texto | cláusulas candidatas por código | em memória (ver 3.1) |
| 4 | Empacotamento | Aplicação | pré-codificado | pacote QDPX e sugestões | `2_processamento/qdpx/` |
| 5 | Validação | Técnico por tema | QDPX importado no MAXQDA | export individual | `3_analise/mqex/` |
| 6 | Integração | Responsável de integração | MQEX da semana | master atualizado e linha no log | `3_analise/master/` |
| 7 | Entrega às peritas | Coordenação | master | XLSX por tema | `4_temas/{TEMA}/` |
| 8 | Redação | Perita | XLSX do tema | texto do capítulo | `5_redacao/` |

Cinco regras sustentam esta sequência.

A fase 1 é a única em que se atribui nome. Nas fases 2 a 4 o nome é herdado pela aplicação. Renomear a meio quebra a rastreabilidade sem produzir erro visível, porque a aplicação lê do nome do ficheiro o ano, o boletim e as partes.

Só a família `convencoes/` atravessa as fases 2 a 8. As portarias de extensão e os acordos de adesão param na fase 1 (ver 4.6).

Depois de integrado no master, o MQEX vai para `9_arquivo/`. Nunca permanece em `3_analise/mqex/`, para que essa pasta signifique sempre «por integrar».

Cada integração escreve uma linha em `logs_integracao/` com data, ficheiro, responsável, número de segmentos e conflitos resolvidos. É o que permite reconstruir o master a partir dos MQEX arquivados.

`1_fontes/` é de leitura apenas. Um PDF defeituoso regista-se no catálogo e trata-se a jusante, sem corrigir o original.

### 3.1 Correspondência com as pastas da aplicação

A árvore do RNC é o arquivo partilhado e de longa duração do projeto. A árvore da aplicação, documentada em [organização do workspace](../dados/organizacao-workspace.md), é a da máquina onde a aplicação corre. A correspondência é esta:

| Pasta do RNC | Pasta da aplicação | Como se passa de uma à outra |
|---|---|---|
| `1_fontes/indices_bte/` | `data/raw/indices/` | cópia, ou a mesma pasta por atalho |
| `1_fontes/irct/{FAMILIA}/` | `data/raw/bte/bte_2026/{FAMILIA}/` | `python -m cct.nomeacao --esquema rnc` |
| `1_fontes/bte_completo/` | `data/raw/bte/bte_<ano>/`, no formato «números completos» | usado nos anos históricos, pelo `cct/localizador.py` |
| `1_fontes/externas/` | sem pasta própria | os scripts de vocabulários leem o ficheiro onde ele estiver; o que persiste é o vocabulário construído |
| `2_processamento/qdpx/` | `results/runs/<ano>/<id>/projeto.qdpx` | saída do `cct.pipeline_tema` |
| `3_analise/comparacoes/` | `results/benchmarks/<tema>/comparacoes/` | `python -m cct.comparar` |
| `0_gestao/catalogo/` | escrito diretamente | `python -m cct.catalogo --saida …` |
| `0_gestao/vocabularios/` | `vocabularios/` do repositório | versionado com o código (ver 7) |

**Nota sobre `2_processamento/texto/` e `precodificado/`.** O `cct.pipeline_tema` vai do PDF ao QDPX numa só passagem e mantém o texto extraído e as anotações em memória. Não escreve ficheiros intermédios. As duas pastas existem na árvore para receberem esses ficheiros quando a aplicação passar a escrevê-los, e para receberem extrações feitas à mão durante um diagnóstico. Hoje ficam vazias, e isso está correto. As saídas persistentes de cada execução são `projeto.qdpx`, `sugestoes_peritas.xlsx`, `relatorio.txt` e `manifest.json`. Ao promover uma execução para o arquivo, o QDPX recebe o nome do lote e o manifesto acompanha-o.

Cada execução da aplicação é datada e descartável. O que fica no arquivo do RNC é a execução que gerou o QDPX importado no master, e o respetivo `manifest.json`, que regista o comando, o commit, as versões, os hashes das entradas e saídas, as contagens e os problemas encontrados.

---

## 4. Convenção de nomes

### 4.1 A regra

```text
{ANO}_{AMBITO}_{SEQ}_{TIPO}_{CODIRCT}_BTE_{NN}_{SIGLAS}
```

| Elemento | Conteúdo | Origem no índice do BTE | Exemplo |
|---|---|---|---|
| `ANO` | ano de publicação, 4 dígitos | `Ano` | `2026` |
| `AMBITO` | PRI, SPE ou APU (ver 4.3) | inferido, com vocabulário | `PRI` |
| `SEQ` | n.º sequencial do ano, 3 dígitos | `IDDocumento` (`377/2026` dá `377`) | `377` |
| `TIPO` | tipo de documento, sem tradução | `TipoSubTipoDoc` | `CCT-ALT` |
| `CODIRCT` | código da convenção, estável entre revisões (ver 4.4) | `CodigoGEPDGERT` | `27251` |
| `NN` | número do boletim, 2 dígitos | `NBTE` | `31` |
| `SIGLAS` | até 3 siglas das partes, separadas por hífen; havendo mais, `+N` | `Outorgantes` | `ACRAL-CESP-STRUP+2` |

Sem acentos, sem espaços, sem cedilhas. **Máximo de 63 caracteres**, que é o limite de nome de documento do MAXQDA: um nome mais longo é truncado na importação e quebra o cruzamento com as variáveis de documento. Quando não cabe, a aplicação encurta as siglas, nunca o prefixo, e assinala que o fez.

O número sequencial é o atribuído pela DGCP, sem o ano, por decisão de compatibilidade: os códigos do RNC devem coincidir ao máximo com os que já existem, e este é o número pelo qual o próprio boletim cita o documento e pelo qual as cadeias de alteração o referem (`CCT-ALT.20250708.321/2025`). O ordinal interno da aplicação subsiste apenas como recurso: quando o índice não traz `IDDocumento`, a linha fica marcada `por_confirmar` e o ficheiro não é escrito.

O campo `_BTE_{NN}` é um acrescento face à convenção publicada na v2.1, fundamentado em [ADR-0016](../adr/0016-esquema-de-nomes-do-rnc.md). Permite voltar do ficheiro ao boletim sem consultar o catálogo e é o que a aplicação lê para emparelhar versões.

Os dois esquemas de nome coexistem. Um corpus pode ter nomes de 2025 (`26_PR_003_BTE_31_ACRAL_CESP`) e deste esquema, e a aplicação lê ambos.

### 4.2 Nomes das outras famílias de ficheiro

| Família | Padrão | Exemplo |
|---|---|---|
| Índice BTE recebido | `AAAA_BTE_NN_indice.xlsx` | `2026_BTE_31_indice.xlsx` |
| BTE completo | `AAAA_BTE_NN.pdf` | `2026_BTE_31.pdf` |
| Lote QDPX | `RNC_AAAA_lote_NN.qdpx` | `RNC_2026_lote_03.qdpx` |
| Export individual MAXQDA | `AAAA_{TEMA}_{INICIAIS}_AAAAMMDD.mqex` | `2026_C9-SALARIOS_AF_20270315.mqex` |
| Projeto master | `RNC_Dados_AAAA_master.mqda` | `RNC_Dados_2026_master.mqda` |
| Export por tema | `AAAA_{TEMA}_{CONTEUDO}_AAAAMMDD.xlsx` | `2026_C9-SALARIOS_segcod_20270401.xlsx` |
| Capítulo | `{codigo_roteiro}_{titulo_curto}.docx` | `4_07_remuneracoes.docx` |
| Relatório consolidado | `RNC_Dados_AAAA_AAAAMMDD.docx` | `RNC_Dados_2026_20270930.docx` |
| Catálogo | `catalogo_irct_AAAA.csv` | `catalogo_irct_2026.csv` |

`{CONTEUDO}` pertence a um vocabulário fechado: `segcod` (segmentos codificados), `matriz` (matriz de códigos), `vardoc` (variáveis de documento), `quadros`, `graficos`.

A versão ativa de um capítulo não leva data, e é assim que se reconhece. As anteriores levam data e ficam em `9_arquivo/`.

### 4.3 Âmbito

A aplicação processa convenções do sector privado e do sector público empresarial. Não processa ainda as da Administração Pública, cujos IRCT são celebrados ao abrigo da LTFP e depositados na DGAEP. Enquanto assim for, é preciso distinguir à entrada o que entra no pipeline do que fica apenas recolhido. O número sequencial do BTE não serve para isso, porque é uma série única que atravessa tudo.

| Valor | Conteúdo | Processável |
|---|---|---|
| `PRI` | Sector privado | sim |
| `SPE` | Sector público empresarial: EPE, EM, SA de capitais públicos | sim |
| `APU` | Administração Pública: ACT e ACEP ao abrigo da LTFP | não, ainda |

São três letras e não duas por uma razão: o `PU` usado em 2025 significava «público empresarial» mas lia-se como «público».

O âmbito não consta do índice. A aplicação propõe-o por quatro vias, pela ordem da fiabilidade.

1. **Vocabulário da equipa** (`empregadores_ambito.csv`). É a única via que decide sem aviso.
2. **Lista do INE** das entidades do sector institucional S.13. Propõe, não decide (ver 4.3.1).
3. **Regra**: o tipo `ACEP` indica APU; as formas `, EPE`, `, EM` e «Empresa Municipal» indicam SPE; município, câmara, freguesia, universidade, politécnico e direção-geral indicam APU.
4. **Omissão**: PRI, registado como `omissao`.

Tudo o que a regra ou a lista do INE classifiquem como SPE ou APU sai com aviso e fica por rever. A aplicação nunca decide um APU sem aviso, porque um falso APU retira um documento do pipeline sem que isso seja detetado. A coluna `ambito_origem` do catálogo regista qual das quatro vias decidiu.

O âmbito subdivide fisicamente a pasta das convenções, em `PRI/`, `SPE/` e `APU/`. Assim a incapacidade de processar a Administração Pública passa a ser a estrutura das pastas e não uma nota num documento.

#### 4.3.1 A lista do INE

O INE publica anualmente as **Entidades do Setor Institucional das Administrações Públicas**, 4.241 entidades em 2025, em doze subsectores do S.13 nos termos do SEC 2010. Está importada em `vocabularios/entidades_administracao_publica.csv`.

O critério do INE é de contas nacionais: uma entidade integra o S.13 se for produtor não mercantil, o que se decide pelo teste dos 50% de cobertura dos custos por receitas de mercado. O critério do RNC é de regime laboral: são APU as entidades cujos trabalhadores estão sob a LTFP e cujos IRCT vão para a DGAEP. Os dois critérios divergem em ambos os sentidos.

| Entidade | Integra o S.13 | Âmbito no RNC |
|---|---|---|
| Metropolitano de Lisboa, E.P.E. | sim | SPE: trabalhadores sob o Código do Trabalho, AE publicado no BTE |
| Rádio e Televisão de Portugal, S.A. | sim | SPE |
| Infraestruturas de Portugal, S.A. | sim | SPE |
| TUB, Transportes Urbanos de Braga, E.M. | sim | SPE |
| CP, Carris, EPAL, Águas de Portugal | não | SPE: passam o teste de mercado |
| Empresa Metropolitana de Estacionamento da Maia, E.M. | não | SPE, processada a partir do BTE 31/2026 |

Se a lista decidisse, 174 entidades sairiam do pipeline como falsos APU. Por isso entra com duas camadas de sinal: as 4.067 entidades sem forma jurídica empresarial propõem APU; as 174 com forma jurídica empresarial, que são empresas públicas reclassificadas em contas nacionais, propõem SPE e nunca APU. Toda a proposta vinda da lista sai com aviso, mesmo quando acerta, e a ausência da lista não constitui sinal de nada. Fundamentação em [ADR-0019](../adr/0019-lista-do-ine-como-sinal-de-ambito.md).

Continua a fazer falta uma lista da DGAEP com as entidades cujos trabalhadores estão sob a LTFP, que responderia diretamente à pergunta do RNC.

### 4.4 Código IRCT

O `COD: (IRCT)` publicado no BTE é o identificador de acto de negociação da DGERT com um dígito de família antecedido: `27251` corresponde ao acto `7251` (contrato coletivo) e `47252` ao acto `7252` (acordo de empresa). Esse identificador é estável entre revisões da mesma convenção ao longo dos anos, o que foi verificado por cruzamento do índice do BTE 31/2026 com a folha «Negociação coletiva» do registo da DGERT: dos 1.860 actos do registo, 1.110 abrangem mais do que um ano, e o acto 6651 (AEVP com a FESAHT) vai de 2018 a 2026.

É isto que permite reunir toda a história de uma convenção com `ls 1_fontes/irct/convencoes/*/*_27251_*`, e ligar o trabalho do RNC ao registo da DGERT através da coluna `acto_negociacao` do catálogo.

Estão verificados dois dígitos de família, o `2` e o `4`. Os dígitos dos acordos coletivos de trabalho, portarias de extensão, acordos de adesão e decisões arbitrais não estão determinados, e a DGCP não publica a tabela. A aplicação não os infere: um código de cinco algarismos cuja família não esteja verificada sai com `acto_negociacao` vazio, ficando o código completo na coluna `cod_irct`. Uma coluna vazia é visível; uma junção errada com o registo da DGERT não é.

### 4.5 Siglas

Duas situações distintas, com respostas distintas.

**Siglas em falta.** Nem toda a entidade tem sigla no registo da DGERT, sobretudo as empresas em acordos de empresa. A aplicação deriva um nome pouco legível (`EmpresaMetropolitana`, `APSolutionsGMBH`), marca a linha como `por_confirmar` e não escreve o ficheiro. Resolve-se acrescentando uma linha à tabela da equipa.

**Siglas duplicadas.** Das 2.403 organizações do registo, 391 siglas são pedidas por mais do que uma organização distinta. Decidir caso a caso produziria `SNM` num ficheiro e `SNMot` noutro consoante quem processasse o boletim, e um nome atribuído não muda. A desambiguação é feita por uma escada de candidatos, percorrida por ordem até encontrar um livre:

```text
1. SIGLA                         SNM
2. SIGLA + palavra distintiva    SNMotoristas
3. SIGLA + concelho da sede      SNMLisboa
4. SIGLA + 1.ª e 2.ª palavras
5. SIGLA + código DGERT          SNM14021       garantidamente único
```

Quatro propriedades tornam a regra utilizável. Só se altera o que colide, pelo que uma sigla usada por uma única organização permanece como está. Fica com o primeiro degrau a linhagem de código DGERT mais baixo, que é a mais antiga no registo, e não a primeira a ser processada, pelo que o resultado não depende da ordem. A unicidade ignora maiúsculas, porque em Windows e macOS `SNMotoristas` e `SNMOTORISTAS` designam o mesmo ficheiro. E uma sigla atribuída não é reatribuída: o construtor fixa o vocabulário anterior, e recalcular tudo exige `--reatribuir`.

O construtor falha, em vez de avisar, se restar um duplicado, porque a escada só termina em candidatos livres e um duplicado restante indica defeito na regra.

Gerações da mesma organização não constituem conflito: o SITESE mudou de nome seis vezes e continua a ser o SITESE. A linhagem lê-se dos dois primeiros componentes do código DGERT.

Medição sobre o export de 16/09/2026: 2.403 organizações, 2.009 siglas distintas à saída, 391 desambiguadas, nenhum duplicado. A coluna `sigla_base` guarda a sigla original e a `origem_sigla` regista a desambiguação. Fundamentação em [ADR-0017](../adr/0017-regra-de-desambiguacao-de-siglas.md).

O exemplo `SNM` ilustra a regra sem ser uma saída real, porque no registo da DGERT o Sindicato Nacional dos Motoristas não tem acrónimo. Saídas reais: `ACE` dá `ACEAbrantes`, `AIM` dá `AIMoagem`, `AES` dá `AESines`, `ACIS` dá `ACISBeira`, e `AIT` dá `AITomate` e `AITLisboa` para duas associações distintas de industriais de tomate.

### 4.6 Famílias documentais

O BTE publica quatro tipos de documento sob a designação genérica de IRCT.

| Família | Tipos | Natureza | Tem articulado |
|---|---|---|---|
| `convencao` | CCT, ACT, ACEP, AE, DA | o articulado, e a decisão arbitral que o substitui | sim |
| `extensao` | PE, PCT, PRT | acto do Governo que alarga o âmbito de uma convenção a quem não está filiado nas partes | não |
| `adesao` | AA | uma parte adere a convenção de que não era outorgante | não |
| `aviso` | AVISO, AV | projeto de portaria, denúncia, caducidade | não |

Uma portaria de extensão tem dois ou três artigos sobre âmbito e produção de efeitos, sem cláusula de retribuição, de tempo de trabalho ou qualquer outra que o livro de códigos procure. Codificá-la como convenção produz contagens erradas sem produzir erro.

Cada família tem a sua pasta. O âmbito subdivide apenas as convenções, porque o que o âmbito decide é se o documento entra no pipeline e nenhuma portaria ou adesão entra. O âmbito continua a constar do nome de todos os ficheiros.

Os avisos não têm pasta. Ficam registados na coluna `avisos_projeto` da portaria a que correspondem, ligados pela convenção que ambos referem. A linha de catálogo do aviso mantém-se, com `estado=metadado`.

As portarias, adesões e avisos param na fase 1 do ciclo de vida. São recolhidos, nomeados e catalogados, e ficam disponíveis para consulta e contagem. A coluna `processavel` cruza as duas condições:

| | família `convencao` | portaria ou adesão | aviso |
|---|---|---|---|
| âmbito PRI ou SPE | processável | recolhido, não processado | só metadado |
| âmbito APU | recolhido, não processado | recolhido, não processado | só metadado |

O `cct.pipeline_tema` recusa-se a correr se a pasta de entrada contiver um ficheiro de outra família, indicando para onde apontar. Um tipo que o vocabulário não conheça fica em `por_classificar/` e consta do relatório. Fundamentação em [ADR-0018](../adr/0018-familias-documentais-em-pastas-separadas.md).

---

## 5. Temas

Os temas são um vocabulário e não uma arrumação. Vivem num único ficheiro, `vocabularios/temas.csv`, com as colunas `codigo_roteiro`, `descricao_roteiro`, `codigo_europeu`, `nivel`, `ativo_em`, `perita_responsavel` e `codebook`.

A razão é a transição em curso para o modelo europeu (Eurofound, OCDE, WageIndicator), que substitui os pontos do roteiro atual (4.5 a 4.20) por 12 macro temas (`C1_PROFISSOES` a `C12_TECNOLOGIA_VERDE`), com metadados de nível 1 e classificação de cláusulas de nível 3. Com os temas nos nomes das pastas, como estavam no SOP v1.0 e no README v1, a transição obrigaria a mexer em toda a árvore de ficheiros e em todas as ligações que dela dependem. Assim, mudar de modelo passa a ser editar um CSV. As séries históricas mantêm-se porque as duas colunas de código coexistem.

A coluna `codebook` liga o vocabulário à aplicação: um tema novo é um ficheiro YAML em `codebooks/`, nunca uma alteração ao código, e o `temas.csv` diz qual é o YAML de cada tema.

A única exceção é `4_temas/`, que usa o tema no nome por ser o ponto de entrega a pessoas externas. Cada perita recebe a sua pasta e não precisa de navegar o resto.

```text
4_temas/
├── C9-SALARIOS/
│   ├── 2026_C9-SALARIOS_segcod_20270401.xlsx
│   ├── 2026_C9-SALARIOS_matriz_20270401.xlsx
│   └── LEIAME.md          gerado: âmbito do tema, códigos, prazo, contacto
└── C10-TEMPO-TRAB/
```

Estas pastas são geradas a partir do `temas.csv` e nunca criadas à mão. Se no ano seguinte os temas forem outros, apagam-se e regeneram-se, sem afetar o resto da estrutura. Se um tema não consta do `temas.csv`, o que falta é a linha no `temas.csv`.

---

## 6. Catálogo

`0_gestao/catalogo/catalogo_irct_2026.csv` tem uma linha por documento e é gerado pela aplicação a partir dos índices do BTE:

```bash
python -m cct.catalogo \
    --indices 1_fontes/indices_bte \
    --saida 0_gestao/catalogo/catalogo_irct_2026.csv \
    --siglas 0_gestao/vocabularios/siglas_equipa.csv \
    --siglas vocabularios/siglas_organizacoes.csv
```

São 30 colunas produzidas automaticamente: `nome_canonico`, `ficheiro_destino`, `ficheiro_origem`, `ano`, `seq_anual`, `tipo_documento`, `familia`, `processavel`, `ambito`, `ambito_origem`, `cod_irct`, `acto_negociacao`, `bte_numero`, `bte_data`, `pagina_inicio`, `pagina_fim`, `n_outorgantes`, `outorgantes`, `relacao`, `relacao_alvo`, `avisos_projeto`, `altera_estruturado`, `altera_por_resolver`, `vide_em_vigor`, `materias_detectadas`, `sectores_a_classificar`, `url_fonte`, `titulo`, `estado` e `avisos`.

E cinco colunas preenchidas pela equipa ao longo do ciclo: `temas_atribuidos`, `tecnico`, `data_validacao`, `perita` e `observacoes`.

Regerar o catálogo não apaga trabalho humano. As cinco colunas da equipa são recuperadas do catálogo anterior pelo `nome_canonico`, que por convenção não muda. Uma linha que deixe de aparecer nos índices é mantida com o aviso «já não consta dos índices lidos, verificar», porque um documento que desaparece de um índice é facto a investigar.

Este catálogo não substitui a lista SharePoint proposta no SOP v1.0: alimenta-a. A diferença é que a fonte de verdade passa a ser um ficheiro versionável e regerável.

### 6.1 Relações entre documentos

A coluna de alterações do índice tem formato regular, `CCT-ALT.20250708.321/2025`, com tipo, data e sequencial do ano do documento alterado. Os 13 valores presentes no BTE 31/2026 correspondem todos ao padrão. A aplicação separa-os em `altera_estruturado` e `altera_por_resolver`.

O dialeto técnico do índice parte esta cadeia em duas colunas, `DocAlteradosPorEste` e `DocAlteradosPorEste2`. A aplicação junta-as; ler apenas a primeira perderia metade da cadeia sem o assinalar.

O que o documento faz à convenção a que se refere consta das colunas `relacao` e `relacao_alvo`. A distinção não se lê da coluna do índice, cujo formato é igual nos quatro casos, mas do tipo do documento:

| `relacao` | Quando | Significado |
|---|---|---|
| `altera` | CCT-ALT, AE-ALT | revisão do próprio articulado |
| `estende` | PE, PCT, PRT | alarga o âmbito da convenção a terceiros |
| `adere` | AA | uma parte passa a estar abrangida |
| `refere` | AVISO | menciona, sem produzir efeito |

Sem esta distinção, uma contagem de revisões de uma convenção incluiria portarias que nunca lhe alteraram o articulado.

### 6.2 Sectores e matérias

A coluna dos sectores do índice mistura dois vocabulários. No BTE 31/2026, «VINHOS E BEBIDAS ESPIRITUOSAS», «VITICULTURA» e «COMÉRCIO POR GROSSO DE BEBIDAS» são sectores, enquanto «REMUNERAÇÕES» e «SUBSÍDIO DE REFEIÇÃO» são matérias reguladas.

A aplicação reconhece as matérias, que constituem um conjunto pequeno e fechado, o do livro de códigos, e trata como candidato a sector tudo o resto, em `sectores_a_classificar`. Nada é descartado e nada é assumido: cada item cai num dos dois lados, e o lado não reconhecido fica explicitamente marcado para decisão humana.

Reconhecem-se matérias e não sectores porque as matérias são estáveis e poucas, enquanto os sectores são abertos e acompanham a CAE. Uma lista de sectores desatualizar-se-ia sem o assinalar; uma lista de matérias, quando falha, envia o item para revisão.

Falta decidir se os sectores passam a CAE ou NACE, o que é decisão de equipa e não técnica. A coluna `sectores_a_classificar` é o material de trabalho para essa decisão.

### 6.3 Páginas

O nome que o BTE atribui ao PDF codifica o intervalo de páginas em dois blocos de quatro dígitos: `00260057.pdf` corresponde às páginas 26 a 57. A aplicação extrai-o. No BTE 31/2026 os 14 intervalos são contíguos e cobrem as páginas 26 a 179 sem sobreposição nem lacuna. A coluna `PagVersaoEscrita` do índice vem vazia neste dialeto, pelo que sem esta extração o catálogo ficaria sem páginas.

---

## 7. Vocabulários controlados

Todos em `vocabularios/`, em CSV com separador `;` e UTF-8, versionados com o código. Na árvore do RNC vivem em `0_gestao/vocabularios/`, e são o mesmo ficheiro.

| Ficheiro | Conteúdo | Estado |
|---|---|---|
| `siglas_organizacoes.csv` | 2.403 organizações com sigla canónica sem duplicados, sigla de origem, tipo, lado, concelho e estado | produzido |
| `siglas_ambiguas.csv` | verificação: fica vazio se a regra de desambiguação funcionou | produzido |
| `actos_negociacao.csv` | 1.860 actos de negociação, com o primeiro e o último ano de cada um | produzido |
| `entidades_administracao_publica.csv` | 4.241 entidades do sector institucional S.13 (INE, 2025), em duas camadas de sinal | produzido |
| `tipos_documento.csv` | universo de tipos do BTE, com família e se altera outro documento | produzido |
| `estados.csv` | estados por que um documento passa, com quem o move e quando | produzido |
| `empregadores_ambito.csv` | empregadores com âmbito conhecido | semente com 10 entradas, por completar |
| `temas.csv` | crosswalk roteiro, macro temas europeus e codebook | incompleto (ver 9) |

Reconstroem-se com:

```bash
python scripts/construir_vocabularios.py 1_fontes/externas/data-export_….xlsx
python scripts/construir_entidades_publicas.py 1_fontes/externas/Entidades_S13_2025.pdf --ano 2025
```

O primeiro comando não altera as siglas já atribuídas: lê o vocabulário anterior e fixa-o, acrescentando apenas as organizações novas. Recalcular tudo exige `--reatribuir`, que altera siglas em uso.

A coluna `origem_sigla` declara de onde veio cada sigla: `registo` (1.360 linhas, acrónimo constante do registo da DGERT), `derivada` (26, extraída da denominação por padrão fiável) ou `recurso` (1.017, construída pela aplicação em CamelCase das palavras significativas). Qualquer destas pode vir com o sufixo `+desambiguada`.

A aplicação não carrega as de origem `recurso`. Carregá-las suprimiria o aviso de confirmação e converteria uma construção automática em facto estabelecido. Permanecem no ficheiro, para que se veja o que falta, e promovem-se alterando `origem_sigla` para `equipa` depois de revistas.

**Regra geral:** um valor que não conste do vocabulário acrescenta-se ao vocabulário, com data e responsável. É o que impede que «Teletrabalho», «teletrabalho» e «Tele-trabalho» coexistam como valores distintos.

---

## 8. Regras de higiene

1. Não editar ficheiros em `1_fontes/`. O que chegou de fora fica como chegou.
2. Uma versão ativa por documento. As anteriores vão para `9_arquivo/` com data no nome.
3. Não duplicar. Se um ficheiro é necessário em dois sítios, referencia-se o caminho.
4. Limpar antes de arquivar: `Thumbs.db`, `.DS_Store`, `~$*.docx`, atalhos `.url`.
5. Máximo de quatro níveis de pastas. Se parecer necessário um quinto, o que falta é um ficheiro-índice.
6. Nomes apenas com letras sem acento, dígitos, `_`, `-` e o `+` do contador de outorgantes. O sublinhado separa campos; o hífen separa itens dentro de um campo.
7. Sem dados pessoais nos nomes de ficheiro. As siglas são de organizações. As iniciais de quem valida aparecem nos `.mqex` e no log de integração.

### 8.1 Os dois dialetos do índice

A DGERT distribui o índice do BTE em dois formatos de cabeçalho, sem qualquer campo relevante em comum além de `Ano`, `CAE` e `Outorgantes`.

| Campo | Dialeto de rótulo (2025) | Dialeto técnico (2026) |
|---|---|---|
| tipo | `TIPO DE DOCUMENTO:` | `TipoSubTipoDoc` |
| código | `COD: (IRCT)` | `CodigoGEPDGERT` |
| boletim | `Nº DO BOLETIM:` | `NBTE` |
| ficheiro | `Página (criado)` | `NomePDF` |
| ligação | `Link para o documento (CRIADO)` | `URLPDF` |

A aplicação lê os dois: cada campo interno aceita os equivalentes de ambos os lados, e a comparação faz-se sobre o nome normalizado, sem acentos, pontuação nem maiúsculas, e não pela posição da coluna. Um cabeçalho desconhecido deixa a coluna vazia e o problema consta do relatório.

### 8.2 Limites do registo da DGERT

O `data-export_….xlsx` não cobre a Administração Pública, o que foi verificado: zero registos com tipo ACEP; zero municípios, câmaras, freguesias, universidades ou politécnicos no registo de empregadores; as únicas categorias existentes são associação, federação, união e confederação de empregadores; e os 1.358 «Acordo coletivo de trabalho» são todos do privado, ao abrigo do artigo 2.º do Código do Trabalho e não da LTFP.

A razão é estrutural: um município não é uma associação de empregadores, e os IRCT da Administração Pública são depositados na DGAEP.

Daí três consequências. A tabela de siglas cobre bem o lado sindical, incluindo SINTAP, FESAP, FNSTFPS e STAL, que negoceiam também no privado, mas não tem empregadores públicos, que terão de ser acrescentados à medida que apareçam. Qualquer estatística de cobertura calculada a partir deste export respeita ao sector privado e público empresarial, e tem de o declarar. E processar a Administração Pública exigirá uma segunda fonte, do lado da DGAEP, para a qual o campo `APU` já está preparado.

A coluna `Ativa ou Extinta` do registo indica o estado de registo e não de atividade: há organizações marcadas «Activa» sem atividade registada há mais de dez anos. Para saber se uma organização está em atividade, usa-se a coluna `ultima_atividade`, que o `siglas_organizacoes.csv` transporta.

---

## 9. O que falta fazer

| # | Tarefa | Esforço | Depende de |
|---|---|---|---|
| 1 | Completar o `temas.csv` a partir do `plano_transicao_livro_codigos_europeu.xlsx`, que tem o mapeamento dos pontos 4.5 a 4.20 para os 12 macro temas. Sem ele, `4_temas/` não se gera. | 1 dia | ficheiro que não está no repositório |
| 2 | Obter da DGCP a tabela de famílias do `COD: (IRCT)`, ou inferir os dígitos em falta a partir de boletins que tragam um ACT e uma portaria de extensão. | meio dia com a tabela; 1 dia por inferência | DGCP, ou 3 a 4 índices do BTE |
| 3 | Verificar portarias de extensão e acordos de adesão com dados reais. A leitura da relação com a convenção-base está implementada e testada contra um índice de ensaio, porque o BTE 31/2026 não traz nenhum destes documentos. Confirmar onde a DGERT regista a convenção estendida, e se o `COD: (IRCT)` de uma portaria é o da convenção ou próprio. | meio dia | um boletim que os traga |
| 4 | Rever as 174 entidades com forma empresarial em S.13 e fixá-las no `empregadores_ambito.csv`. A lista está feita. | 1 dia | equipa |
| 5 | Decidir se os sectores passam a CAE ou NACE. A separação entre sectores e matérias já está feita. | meio dia e decisão de equipa | equipa |
| 6 | Rever as 391 siglas desambiguadas e promover as de origem `recurso` que forem adequadas. A regra garante ausência de duplicados, não que a sigla escolhida seja a preferida pela equipa. | 1 dia | equipa |
| 7 | Migrar o ciclo anterior para esta estrutura (ver 10). | 2 a 3 dias | equipa |

Nenhuma destas tarefas impede começar o ciclo de 2026. Apenas as tarefas 1, 2 e 3 dependem de informação que ainda não existe no projeto.

---

## 10. Migração do ciclo anterior

| Ciclo 2025 (SOP v1.0 e README v1) | Estrutura atual |
|---|---|
| `01_roteiro/` | `0_gestao/roteiro/` e `0_gestao/livro_codigos/` |
| `02_recolha/bte/` | `1_fontes/bte_completo/` |
| `02_recolha/convencoes/por_sigla/` | `1_fontes/irct/convencoes/{AMBITO}/` |
| `02_recolha/fontes_primarias/` | `1_fontes/externas/` |
| `03_analise/maxqda/` | `3_analise/master/` e `3_analise/mqex/` |
| `03_analise/comparacoes/` | `3_analise/comparacoes/` |
| `03_analise/temas_transversais/NN_tema/` | `4_temas/{CODIGO}/`, gerado a partir do `temas.csv` e não migrado |
| `04_redacao/` | `5_redacao/` e `6_relatorio/` |
| lista SharePoint de metadados | `0_gestao/catalogo/`, que a alimenta |

Na árvore da aplicação, o esquema de 2025 reunia tudo o que não era convenção numa única pasta `data/raw/bte/bte_AAAA/extensoes/`. Ao migrar, esses ficheiros separam-se pelo token de família do nome: `PE` e `AV` para `portarias_extensao/`, `AA` para `acordos_adesao/`. Os avisos deixam de ter ficheiro e passam a constar do catálogo.

**Os nomes não se alteram.** Os ficheiros do ciclo de 2025 mantêm o nome que têm, no formato `26_PR_003_BTE_31_ACRAL_CESP.pdf`, e a aplicação continua a lê-los. O esquema novo aplica-se ao que entra de novo. Migrar a estrutura de pastas é seguro; migrar nomes quebra o trabalho já feito no MAXQDA, que referencia os documentos pelo nome.

---

## 11. Ferramentas

| Comando | Função |
|---|---|
| `python -m cct.recolha` | Lê os índices e descarrega os PDF. Só liga à rede com `--confirmar-rede`, e só para anfitriões de uma lista fechada ([ADR-0015](../adr/0015-recolha-em-rede-desligada-por-omissao.md)) |
| `python -m cct.nomeacao --esquema rnc` | Atribui os nomes canónicos e arruma por família e âmbito. Sem `--aplicar` apenas simula |
| `python -m cct.catalogo` | Escreve o `catalogo_irct_AAAA.csv` |
| `python -m cct.aquisicao` | Encadeia recolha e nomeação, com relatório único |
| `python scripts/construir_vocabularios.py` | Reconstrói os vocabulários a partir do export da DGERT |
| `python scripts/construir_entidades_publicas.py` | Lê a lista anual do INE das entidades do sector S.13 |
| `python -m cct.pipeline_tema` | Extração, pré-codificação, diacronia e triagem, com saída em QDPX |
| `python -m cct.doctor` | Verifica o que falta no ambiente |

### 11.1 Processar um número do BTE

```bash
# 1. simulação: não liga à rede nem escreve ficheiros
python -m cct.recolha --indices 1_fontes/indices_bte

# 2. recolha efetiva (única fase que acede à rede)
python -m cct.recolha --indices 1_fontes/indices_bte --confirmar-rede

# 3. nomear, simulando primeiro para ver os avisos
python -m cct.nomeacao --esquema rnc --destino 1_fontes/irct \
    --siglas 0_gestao/vocabularios/siglas_equipa.csv \
    --siglas vocabularios/siglas_organizacoes.csv \
    --ambitos vocabularios/empregadores_ambito.csv

# 4. resolver os avisos nos vocabulários e só depois aplicar
python -m cct.nomeacao --esquema rnc --destino 1_fontes/irct \
    --siglas 0_gestao/vocabularios/siglas_equipa.csv \
    --siglas vocabularios/siglas_organizacoes.csv \
    --ambitos vocabularios/empregadores_ambito.csv --aplicar

# 5. catálogo
python -m cct.catalogo --indices 1_fontes/indices_bte \
    --saida 0_gestao/catalogo/catalogo_irct_2026.csv \
    --siglas 0_gestao/vocabularios/siglas_equipa.csv \
    --siglas vocabularios/siglas_organizacoes.csv

# 6. pipeline do tema, apenas sobre o que é processável
python -m cct.pipeline_tema \
    --pdfs 1_fontes/irct/convencoes/PRI \
    --codebook codebooks/4_08_protecao_dados.yaml \
    --out 2_processamento
```

A nomeação não escreve um ficheiro cujo nome dependa de sigla derivada por heurística: o passo 3 mostra o que falta e o passo 4 resolve. Quem aceite o risco conscientemente, numa execução em lote já revista, usa `--aceitar-heuristicas`. A bandeira `--siglas` é repetível, e em caso de conflito ganha o primeiro ficheiro indicado, pelo que a tabela da equipa deve vir antes da tabela gerada.

Os boletins processam-se por ordem crescente, acumulando o catálogo.

### 11.2 Estado verificado (BTE 31/2026, 14 documentos)

| Verificação | Resultado |
|---|---|
| Linhas lidas do índice no dialeto técnico | 14 de 14 |
| Nomes canónicos gerados | 14 de 14 |
| Nomes com mais de 63 caracteres | nenhum; o mais longo tem 59 |
| Colisões de nome | nenhuma |
| Nomes aceites pelo `cct.localizador` | 14 de 14 |
| Relações de alteração processadas | 13 de 13 |
| Páginas extraídas do nome de origem | 14 de 14, contíguas de 26 a 179 |
| Retificações resolvidas sem catálogo acumulado | 4 de 4 |
| Âmbitos SPE detetados | 5, sendo 1 por regra e 4 por vocabulário |
| Siglas por recurso final | 4, a acrescentar à tabela antes de uso em produção |
| Sectores e matérias separados | 14 de 14, sem perda de itens |
| Siglas duplicadas no vocabulário após a regra | nenhuma, de 391 conflitos |
| Portarias, adesões e avisos | verificados contra índice de ensaio, não contra dados reais (tarefa 3) |

Reproduzível com `python -m pytest tests/test_rnc.py`.

---

## Registo de alterações

**v4.0, 17/09/2026.** Documento renumerado, sem secções `bis` e `ter`. Registo de alterações condensado nesta secção, com a fundamentação de cada decisão remetida para os ADR. Corrigida a correspondência com as pastas da aplicação (ver 3.1): `1_fontes/bte_completo/` corresponde a `data/raw/bte/bte_<ano>/` e não a uma pasta `bte_completo` inexistente; `1_fontes/externas/` não tem pasta correspondente; e `2_processamento/texto/` e `precodificado/` não recebem ficheiros, porque o pipeline mantém o intermédio em memória. Corrigida a tabela de migração (ver 10). Secção «O que falta fazer» reduzida ao que efetivamente falta.

**v3.x, 16/09/2026.** Compatibilização com a AppCCT, integrada em [PR #43](https://github.com/calvicius-af/crl-app-cct/pull/43):

1. Convenção de nomes com sete campos, incluindo o número do boletim ([ADR-0016](../adr/0016-esquema-de-nomes-do-rnc.md)), limite de 63 caracteres e número sequencial da DGCP.
2. Código IRCT confirmado como estável entre revisões, com o método de verificação em 4.4. A v2.1 dava esta questão como bloqueante.
3. Retificações resolvidas a partir do título, sem necessidade de catálogo acumulado. A v2.1 dava esta questão como bloqueante.
4. Sectores e matérias separados por omissão, com o não reconhecido marcado para decisão humana. A v2.1 dava esta questão como bloqueante.
5. Siglas duplicadas resolvidas por regra determinística ([ADR-0017](../adr/0017-regra-de-desambiguacao-de-siglas.md)).
6. Famílias documentais em pastas separadas, com apenas as convenções no pipeline ([ADR-0018](../adr/0018-familias-documentais-em-pastas-separadas.md)).
7. Lista do INE importada como sinal de âmbito, nunca como decisão ([ADR-0019](../adr/0019-lista-do-ine-como-sinal-de-ambito.md)).
8. Catálogo gerado pela aplicação, com testes, substituindo a ferramenta externa `catalogar_bte.py`.

**v2.1 e anteriores.** Convenção estabelecida em `README.Estrutura_RNC_2027.docx`: árvore por fase do trabalho, âmbito com três letras, código IRCT no nome, temas fora das pastas, pasta `9_arquivo/` explícita, máximo de quatro níveis.

---

## Documentos relacionados

| Documento | Conteúdo |
|---|---|
| [ADR-0016](../adr/0016-esquema-de-nomes-do-rnc.md) | Esquema de nomes, e o que se recusou |
| [ADR-0017](../adr/0017-regra-de-desambiguacao-de-siglas.md) | Regra de desambiguação de siglas |
| [ADR-0018](../adr/0018-familias-documentais-em-pastas-separadas.md) | Famílias documentais em pastas separadas |
| [ADR-0019](../adr/0019-lista-do-ine-como-sinal-de-ambito.md) | Lista do INE como sinal de âmbito |
| [SPEC-0003](../../specs/0003-compatibilizacao-com-a-gestao-documental-do-rnc.md) | O que se construiu, e como se verificou |
| [SPEC-0001](../../specs/0001-recolha-e-nomeacao-do-bte.md) | Recolha e nomeação, antes desta compatibilização |
| [`pastas/`](pastas/) | Um README por pasta principal da árvore |
| [guia de operação](../operacao/guia-operacao.md) | Operação da aplicação |
| [organização do workspace](../dados/organizacao-workspace.md) | Ciclo de vida das pastas da aplicação |

Dúvidas sobre este documento: coordenação do RNC. Alterações à convenção de nomes exigem decisão de equipa e nova versão deste ficheiro, e não se alteram nomes já atribuídos.
