# Organização automática dos documentos — 16 de outubro de 2026

**Registo histórico da primeira correção.** O tratamento dos 11 avisos foi
posteriormente revisto: passaram a ser documentos autónomos. O estado atual
é 411 PDFs organizados, conforme a [validação das tipologias](tipologias-2026-10-16.md).

O índice `BTE_2026_01_10_CRL_b.xlsx` contém 411 documentos. A versão anterior
organizou 87 PDFs, deixou 313 pendentes e classificou 11 avisos como metadados.
Essa primeira versão organizou os 400 documentos com ficheiro canónico, sem
pedidos de confirmação neste lote. Os 11 avisos continuam no catálogo e os seus
PDFs originais permanecem na recolha original.

| Destino        | PDFs |
| -------------- | ---: |
| Convenções PRI | 213  |
| Convenções SPE | 21   |
| Convenções APU | 46   |
| Portarias      | 110  |
| Adesões        | 9    |
| Acórdãos       | 1    |
| Total          | 400  |

## Causas corrigidas

- A referência e data das portarias estavam em `DocumentosEmVigor`, mas a
  nomeação só procurava no título ou num campo interno vazio. O sufixo de série
  `/1` ou `/2` é agora conservado. Há 109 referências com data nessa coluna;
  o documento PE-ALT restante é um aviso sobre uma portaria identificada no título,
  pelo que não se inventa a data de publicação da portaria referida.
- Os 46 acordos de empregador público estavam tipados ACT e sem código DGERT.
  O título determina APU; a identidade publicada do acordo é conservada em
  formato `ACEP12-2026`, sem atribuir um código DGERT fictício.
- As 12 retificações passam a herdar os outorgantes da convenção retificada
  pela referência exata do índice, conservando a origem desse preenchimento.
- Os códigos associados explícitos no índice não exigem nova confirmação
  apenas porque a publicação referida é de outro ano. Contradições entre códigos
  continuam pendentes.
- As variantes PE-ALT e PCT-ALT são aceites, conservando o tipo integral no catálogo.
  Uma PCT sem outorgantes convencionais usa um marcador do tipo no nome.
- A consolidação confundia siglas partilhadas entre denominações diferentes
  com identidade documental ambígua. A nomeação usa a denominação e o ID do
  documento; não associa organizações diferentes só por partilharem sigla.
- Propostas automáticas de abreviatura não são recusas humanas. Nos 206
  documentos que usam pelo menos um rótulo derivado, esse facto fica explícito
  no catálogo e no registo. O estado do vocabulário não é promovido a sigla oficial.
- A lista INE conserva um sinal institucional; não transforma um AE em APU.
- Observações sobre proveniência e encurtamento do nome não bloqueiam a cópia.
  Decisões humanas pendentes, identidades contraditórias, hashes divergentes e
  colisões de ficheiros continuam protegidos.

## Verificação

A suite passou **514 testes**, com **22 ignorados**. Os testes novos incluem
o índice real completo com PDFs sintéticos, as 46 classificações APU, os 12
vínculos de retificação, as referências DR, recusas humanas e códigos contraditórios.
Os testes ignorados não constituem validação das respetivas funcionalidades.

Foi também executada a organização dos PDFs reais numa pasta temporária: 400
cópias com SHA-256 verificado, 87 nomes anteriores preservados, seguida de nova
execução sem duplicados. Este ensaio conservou o registo real intacto.

Depois do ensaio, a operação foi aplicada a `RNC_2026`, através do Python do
ambiente de teste. Foram acrescentados 313 PDFs às pastas canónicas e verificados
os hashes dos 400. Os 87 nomes e caminhos anteriores foram conservados. O catálogo
anterior foi guardado em `0_gestao/catalogo/copias_seguranca/antes_organizacao_20261016T104501Z`.
O relatório antigo de siglas pendentes foi arquivado nessa cópia, para não
continuar a apresentar o estado anterior como se fosse o atual.

A [evidência por documento](organizacao-2026-10-16.json) identifica os destinos,
hashes, proveniência e observações. O resumo da aplicação real está também em
`RNC_2026/0_gestao/catalogo/organizacao_20261016.json`.

## Utilização e alcance

O ambiente de teste foi reinstalado em modo editável para usar o repositório de
desenvolvimento reposto. Fechar e reabrir a GUI carrega as regras atuais. O botão
**Organizar PDFs (sem rede)** reaplica-as a documentos já recolhidos, sem repetir
as descargas. **Conferir / aprovar…** continua reservado ao texto após a conversão;
agora explica o passo em falta quando não existe um lote convertido.

O resultado medido é zero pendentes neste lote de 411 registos. Não demonstra
uma taxa de erro ou de confirmação de um caso por dez milhões de documentos.
Também não certifica as siglas derivadas, a vigência jurídica ou a fidelidade
do Markdown: esses objetivos são diferentes da identificação e organização
dos PDFs a partir do índice.
