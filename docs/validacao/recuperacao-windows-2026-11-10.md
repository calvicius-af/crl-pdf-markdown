# Recuperação do lote Windows — 10/11/2026

## Resultado

O lote de 324 documentos estava conservado no `texto.zip` recebido. O manifesto
ativo apontava apenas para o acórdão processado depois, enquanto os índices
anteriores permaneciam em `_auditoria/corridas`. O desaparecimento da lista de
conferência é explicado pela leitura exclusiva do manifesto ativo.

Foram encontrados quatro índices de execução: 324 documentos em 29/10, um PDF de
teste em 09/11, 324 documentos novamente em 09/11 e um acórdão com OCR nesse dia.
O inventário combinado tem **326 documentos**: o lote, o teste e o acórdão.
Os 324 Markdown e os hashes dos PDFs coincidem entre as duas corridas grandes.
Há diferenças em 108 hashes de extrações Docling e em 16 conjuntos de ocorrências;
os manifestos conservam as observações anteriores, mas o ZIP não contém todas as
versões antigas dessas caches. A recuperação valida os artefactos atuais.

O ZIP não contém as pastas de correções, versões ativas ou decisões humanas,
nem resoluções humanas nos registos inspecionados. Não se pode recuperar uma
edição que não esteja no arquivo nem concluir que existia noutro local.
Nenhuma aprovação foi criada durante a recuperação.

## Preservação e integridade

SHA-256 do ZIP: `700eb31b303da00ee5ded01cb45d8801a3ef1737cd7080e77cb6f57e89911c09`.
O arquivo e a extração original foram conservados. Compararam-se os **1655
ficheiros** extraídos com os bytes do ZIP, sem diferenças.

Criou-se uma cópia de trabalho separada. Nessa cópia, o índice do lote de 324
documentos foi restaurado como ativo, mantendo o acórdão e o teste nos arquivos.
Os relatórios consolidados foram regenerados como derivados; Markdown, extrações
e relatórios individuais recebidos não foram substituídos. A interface nova
reúne também os outros dois documentos através do histórico.

Obtiveram-se 325 PDFs públicos nos URLs do catálogo BTE e verificou-se cada um
contra o SHA-256 recebido. O PDF sintético foi associado a um artefacto local
com hash idêntico. Todos os **326 documentos** do inventário passaram na
verificação de PDF, Markdown e extração; há fontes repetidas por hash.

A GUI local mostrou 326 documentos e o filtro de 68 bloqueados, com a versão
selecionada verificada. Este é um ensaio macOS sobre dados Windows, não a
aceitação do novo instalador numa estação CRL.

## Ocorrências e redução de ruído

No lote de 324: 178 sem alertas, 78 para rever e 68 bloqueados, com **1044
ocorrências**. São avaliações automáticas, não aprovações humanas.

Os 30 documentos com `CRITICAL_SYMBOLS` foram comparados com os PDFs originais
de hash confirmado. Foi identificado e corrigido um falso bloqueio: travessões
em linhas de horários eram contados como sinais negativos. A regra agora exige
evidência restrita de lista de horas válidas; os testes mantêm a deteção de
negativos em prosa, durações, fórmulas, montantes e percentagens.

Na comparação específica de sinais, o alerta desaparece num documento e os
outros 29 mantêm-se. Não foram dispensadas regras globais. Uma reauditoria
completa do caso passou de bloqueado para revisão, com Markdown idêntico e o
aviso de marcadores de lista conservado. O bloqueio anterior permanece no
histórico como ausente por confirmar, com a evidência preservada.

Não se reaplicou esta conclusão automaticamente aos estados do lote recuperado
nem se atribuiu aprovação ao documento. A comparação está registada no
[resumo estruturado](recuperacao-windows-2026-11-10.json).

## Artefactos locais

A evidência extensa fica em `results/recuperacao-windows-20261110`, excluída do Git:

- `texto`: extração original do arquivo, conservada.
- `revisao-recuperada`: cópia de trabalho, com o índice do lote restaurado.
- `originais-verificados`: fontes de conteúdo confirmado por hash.
- `resumo-recuperacao.html`: índice legível dos 326 documentos, com ligações locais.
- `LEIA-ME-recuperacao.md`: instruções para retomar a conferência.
- `comparacao-sinais-completa.json`: comparação dos 30 casos.
- `ensaio-reauditoria-horarios-rc3`: auditoria independente do caso corrigido.

A restauração do índice permite voltar a conferir o lote na aplicação anterior,
mas essa versão pode voltar a trocar o índice numa nova conversão. As proteções
persistentes e a colaboração pertencem ao código 0.4.0rc3 em preparação, cujo
estado de construção e testes está no [PR #20](https://github.com/calvicius-af/crl-pdf-markdown/pull/20).
A recuperação dos documentos não constitui aceitação do instalador.
