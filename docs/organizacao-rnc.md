# Organização e nomes neste fork

Adotado em 13/10/2026 a partir do README RNC v4.0 fornecido em `docs`.
Código, ambiente Python e modelos são locais; os dados podem viver numa pasta
partilhada `RNC_Dados_AAAA`. AAAA é o ano dos dados, não o ano da publicação do relatório.

## Árvore operacional

```text
RNC_Dados_2026/
├── 0_gestao/
│   ├── catalogo/          registo_bte.jsonl, catalogo_irct_2026.csv, nomeacao.csv
│   ├── vocabularios/      siglas.csv e listas complementares
│   └── procedimentos/    guias da equipa; restantes pastas RNC conservadas
├── 1_fontes/
│   ├── indices_bte/       XLSX recebidos
│   ├── bte_completo/      boletins completos históricos
│   ├── externas/          registos de organizações e outras fontes
│   └── irct/
│       ├── convencoes/PRI/, SPE/, APU/
│       ├── portarias_extensao/
│       ├── acordos_adesao/
│       └── acordaos/
├── 2_processamento/
│   ├── recolha_original/  PDF com nome de origem, por ano e BTE
│   ├── texto/            Markdown por documento, com _auditoria separada
│   └── validacao/        relatórios metodológicos do lote
├── 3_analise/
│   ├── revisao_textual/   correções humanas, conservadas
│   ├── corpus_aprovado/  versões conferidas para importar
│   └── master/, mqex/, comparacoes/, logs_integracao/
├── 4_temas/
├── 5_redacao/
├── 6_relatorio/
├── 7_divulgacao/
└── 9_arquivo/
```

`init` cria as pastas em falta e copia vocabulários disponíveis sem substituir
ficheiros existentes. Não move dados legados nem altera as fontes de `docs`.
`collect --workspace` guarda downloads originais em `2_processamento/recolha_original`
e o registo em `0_gestao/catalogo`; `name --aplicar` copia os documentos com nome
canónico para `1_fontes/irct`, conferindo os hashes. Isto evita que as fontes
canónicas sejam escritas com nomes provisórios.

As pastas `precodificado` e `qdpx` da árvore original não são criadas por este
fork, que entrega Markdown. As outras fases do RNC são conservadas como destino
do trabalho da equipa, sem automatizar o MaxQDA ou a redação do relatório.

## Nome adotado

A decisão de 13/10/2026 adota o esquema mais recente do PR #3, ADR-0022,
como omissão em todos os comandos e interfaces de nomeação:

```text
convenção: ANO_BTE_NN_AMBITO_SEQ_TIPO_CODIRCT_SIGLA1-SIGLA2[+N]
2026_BTE_31_PRI_377_CCT_27251_ACRAL-CESP+3.pdf
portaria: ANO_BTE_NN_TIPO_SEQ_NNNN-AAAA_CODIRCT_SIGLA1-SIGLA2[+N]
2026_BTE_31_PE_401_0452-2025_27251_ACRAL-CESP.pdf
adesão: ANO_BTE_NN_AA_SEQ_CODIRCT_SIGLA1-SIGLA2[+N]
acórdão: ANO_BTE_NN_JUR_SEQ_CODIRCT_SIGLA1-SIGLA2[+N]
```

O motor de nomes é único. O esquema anterior do README fornecido, `v4`,
continua disponível por seleção explícita, para compatibilidade:
`ANO_AMBITO_SEQ_TIPO_CODIRCT_BTE_NN_SIGLA1-SIGLA2-SIGLA3[+N]`.
Um nome já atribuído, o seu caminho e o estado de atribuição são preservados.
Trocar de esquema, alterar siglas ou corrigir metadados não renomeia uma fonte
canónica: a proposta fica em conflito para revisão.

Ano e BTE vêm do índice; SEQ vem obrigatoriamente de IDDocumento e tem de ter
o mesmo ano. Nunca se usa um ordinal interno como substituto. O código IRCT
é conservado sem retirar caracteres inválidos. Cada convenção exige uma única
identidade; nas outras famílias é necessário confirmar a convenção de base.
Portarias exigem também a referência completa no Diário da República.

As duas siglas do ADR-0022 representam a primeira entidade patronal e a primeira
sindical; `+N` conta as restantes partes. Identificação incompleta de um lado,
partes retiradas do título, siglas derivadas, relações lidas da cadeia e nomes
encurtados produzem aviso e aguardam confirmação. O limite de 63 caracteres
continua uma restrição do projeto; só as siglas podem ser encurtadas.
Todas as partes e todas as relações continuam no catálogo.

Âmbito: o vocabulário tem prioridade, seguido da lista INE com aviso e das
regras; PRI por omissão fica identificado no catálogo. A lista INE sinaliza o
sector institucional, sem confirmar regime laboral. Classificações SPE/APU por
regra e propostas do INE aguardam revisão. A aplicação de preparação documental
não deduz aprovação de um corpus a partir desse campo.

Os recursos consolidados são incluídos no pacote. `init` copia-os da instalação
para `0_gestao/vocabularios`, independentemente da pasta de execução, e conserva
ficheiros existentes editados pela equipa. A simulação não altera o registo de
recolha nem degrada estados já atribuídos; o catálogo conserva observações da
equipa e regista separadamente o estado da nova proposta.

## Salvaguardas e pendências

- Siglas propostas/ambíguas não entram automaticamente no nome.
- Sem ID, código, outorgantes ou PDF com hash confirmado, fica `por_confirmar`.
- Não há renumeração interna nem substituição de outro PDF com o mesmo nome.
- PE, PCT, PRT, AA e acórdãos podem receber nomes quando os metadados e relações
  de base estão confirmados. Dados em falta ou derivados da cadeia ficam pendentes.
  Avisos têm estado de metadado e não originam ficheiros canónicos.
- No índice 01–10 há referências como `Portaria n.º 457/2025/1` em
  `DocumentosEmVigor`. Este formato não deve ser truncado pelo padrão antigo
  sem uma decisão de representação. Nem a igualdade aparente do código da PE
  com um código de convenção demonstra por si só a relação correta.
- Recortes de boletins completos devem conservar PDF integral e páginas de origem;
  a automatização desse recorte não foi acrescentada nesta intervenção.
- `passed` significa ausência de alertas automáticos; só a revisão documentada
  promove um ficheiro para `3_analise/corpus_aprovado`.

Antes de promover uma corrida, copie a versão conferida e o relatório metodológico
com os hashes. Conserve a pasta da corrida: os relatórios históricos guardam hashes,
mas os links podem apontar para ficheiros posteriormente substituídos com `--overwrite`.
