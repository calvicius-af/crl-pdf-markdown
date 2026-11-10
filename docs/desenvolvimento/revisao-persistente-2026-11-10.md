# Revisão persistente — intervenção de 10/11/2026

## Diagnóstico confirmado no código

A conferência, correção e entrega liam só `_auditoria/manifest.json`, atualizado
em cada execução. Os índices anteriores eram conservados em `corridas`, mas não
eram consultados pela interface de conferência. Assim, um processamento isolado
podia ocultar centenas de documentos ainda presentes no disco.

O `texto.zip` fornecido posteriormente confirmou o mecanismo no lote real:
existem duas corridas de 324 documentos, um ensaio técnico e um acórdão com OCR.
O índice ativo tinha apenas o acórdão. A cópia recuperada volta a apresentar
326 documentos no inventário histórico, com integridade verificada contra os
PDFs e artefactos. Não havia registos de edições ou decisões humanas no ZIP.
Ver [evidência da recuperação](../validacao/recuperacao-windows-2026-11-10.md).

## Alterações implementadas

- Inventário de conferência reconstruído a partir dos manifestos atuais e
  arquivados; o último relatório de execução mantém o seu âmbito original.
- Tentativa incompleta não retira a versão anterior verificável da conferência.
- Conservação do manifesto anterior também para formatos sem arquivo por corrida.
- Recusa antecipada de colisões de PDFs distintos no mesmo nome de saída e de
  substituição de bases com correções ou decisões humanas.
- Guardar/Descartar/Cancelar ao fechar editores e ao fechar a conferência/aplicação;
  notas podem ser guardadas como rascunhos distintos de decisões de aprovação.
- Deteção de gravações concorrentes do mesmo rascunho; retoma de rascunhos guardados
  da mesma pessoa e versão.
- Estados de revisão e gravidades em português na janela de conferência.
- Ação para retomar uma pasta anterior e associação local de PDFs pelos hashes,
  conservando os bytes dos relatórios e decisões.
- Última pasta de conferência e lotes recentes guardados por projeto/utilizador,
  para reencontrar reauditorias depois de fechar, sem alterar as cinco pastas
  principais nem apagar referências temporariamente indisponíveis.
- Correções transferidas são publicadas na pasta atual, conservando o caminho
  original no metadado de proveniência.
- Observações de ocorrências conservadas por versão, com confirmação explícita
  de alertas ausentes, invalidação por alteração da fonte e evidência de autoria.
- Exportação de cópias completas com PDFs verificados e fusão baseada no estado
  de partida, recusando alterações concorrentes incompatíveis e a modificação
  de evidências imutáveis. Importações têm journal, reposição e recuperação.
- Decisões ligadas às anteriores, com deteção de ramos concorrentes e reconciliação
  explícita; não dependem apenas do relógio de cada computador.
- Uma pessoa que corrige a versão de outra recebe um rascunho próprio, com a sua
  autoria; não modifica o rascunho nem assume o nome da pessoa anterior.
- Reauditoria transporta o histórico, conservando a origem e separando evidências
  humanas anteriores de aprovações atuais. `--history` seleciona o inventário;
  a GUI usa esse percurso por omissão.
- Correção de falso bloqueio em marcadores de listas de horários, com sinais
  negativos reais, fórmulas, percentagens e montantes ainda sujeitos a controlo.

O código passou para **0.4.0rc3**, em preparação. Não foi construído nem publicado
um instalador deste candidato nesta intervenção.

## Evidência e limites

O teste de regressão prepara 324 documentos com artefactos verificáveis, conserva
uma aprovação, executa uma seleção isolada com a opção OCR e confirma 325 entradas
na conferência e a entrega do documento aprovado anteriormente. O motor OCR é
substituído neste teste: comprova a preservação do inventário, não a qualidade
do reconhecimento ótico.

Há testes de proteção antes de sobrescrever, recuperação de manifesto arquivado,
gravação concorrente de rascunhos e transferência para uma pasta diferente sem
o PDF no caminho original. O teste de transferência inclui uma correção real
reauditada a partir de cache, com o PDF relocalizado e renomeado.

Os testes Tk exercitam cancelar/guardar ao fechar e recuperar notas sem conceder
aprovação. A sessão gráfica local é macOS; continua necessário ensaio Windows.

Validação local desta intervenção: suíte completa com **667 aprovados e 36
omitidos**; execução Tk explícita com **10 aprovados**; Ruff e Markdownlint sem
erros. A suíte completa foi executada fora da sandbox para permitir o teste de
socket Unix local. As omissões incluem ensaios Windows e corpus condicionais.
O workflow foi preparado para ativar estes ensaios Tk nos runners Windows;
isso não constitui, por si só, evidência de que o workflow já tenha sido executado.

Há testes em dois processos: documentos diferentes conservam ambas as decisões;
no mesmo documento, uma conferência desatualizada é recusada. Uma sobreposição
manual de decisões concorrentes bloqueia a entrega até reconciliação identificada.
Foi testado o regresso de uma correção auditada/aprovada à pasta principal,
incluindo a repetição da importação sem duplicar efeitos e a reposição após falha.

No corpus recebido, compararam-se os sinais numéricos dos **30 PDFs** que tinham
`CRITICAL_SYMBOLS`: um falso bloqueio foi eliminado, mantendo os outros 29 alertas
nessa comparação. A reauditoria completa do caso confirmado passou de bloqueado
para revisão, conservando o Markdown e o aviso restante. A ocorrência antiga
continua no histórico como ausente por confirmar, sem resolução humana inventada.

## Limites e aceitação da distribuição

A transferência foi ensaiada em pastas independentes, com caminhos antigos
indisponíveis, PDFs renomeados e revisores/processos distintos. A conferência
do lote Windows recuperado também foi aberta na GUI local. Isto não representa
um ensaio de um instalador novo em duas estações Windows reais.

Falta construir o instalador 0.4.0rc3 e executar os gates de distribuição Windows
e MAXQDA já definidos no projeto. Não há validação de bloqueios numa partilha CRL
real. O mecanismo de cópias/importação explícita evita depender desses bloqueios
entre máquinas; uma pasta OneDrive não constitui uma base de dados partilhada.

Conflitos de texto exigem conferência e uma nova correção, conservando as duas
cópias. Não se faz fusão automática de conteúdo jurídico. Os modelos de OCR
devem ser escolhidos na máquina onde se executa a extração; não são transportados
nas cópias de revisão. O teste isolado de um falso positivo não demonstra que os
restantes bloqueios sejam todos verdadeiros nem mede a qualidade de todo o corpus.
