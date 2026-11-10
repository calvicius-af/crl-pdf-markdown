# CRL — instalar e abrir no Windows

## O que receber

Um ficheiro `CRL-VERSAO-windows-x64-offline.exe` fornecido pela equipa, com
número de versão. Contém Python, interface gráfica, bibliotecas e modelos,
incluindo OCR. Não é necessário instalar Python, descarregar modelos ou escrever
comandos. O computador precisa de Windows 10/11 x64; a autorização para executar
o programa e as permissões de instalação devem ser confirmadas na estação do CRL.

## Instalar e converter o primeiro PDF

1. Faça duplo clique no instalador. Escolha uma pasta local onde possa instalar
   e acompanhe a barra de progresso. Se o Windows ou as regras do CRL impedirem
   a execução, contacte o apoio; não precisa de alterar essas regras.
   Se o instalador indicar uma incompatibilidade de pasta, escolha uma pasta
   local sem acentos onde tenha permissão. O instalador verifica isto antes de copiar.
2. Abra o atalho **Abrir CRL**, no ambiente de trabalho ou no menu Iniciar.
3. Na configuração inicial, escolha a pasta de trabalho RNC, os índices Excel,
   os PDFs originais, os PDFs nomeados e o Markdown. Podem estar em locais
   diferentes, incluindo `L:`. As escolhas ficam guardadas para as próximas vezes.
4. Prima **PDF…**, escolha o PDF de teste e prima **Construir Markdown**.
   Para digitalizações, ative **OCR**. Aguarde pela indicação de conclusão.
5. Abra a pasta Markdown escolhida e confira o documento e o relatório do lote.
   Os avisos de revisão não equivalem a falhas de instalação.

Para mudar as pastas, use **Configurar pastas…**. O programa não move documentos
já nomeados quando muda uma pasta; conserva os nomes e localizações registados.
Para recolher documentos novos do BTE é necessária Internet; a conversão de
PDFs existentes usa apenas modelos locais.

As ferramentas de recolha, organização, conferência, entrega e reauditoria estão
no separador **Preparar e conferir**. A área **Atividade** tem deslocamento
vertical; pode ler mensagens anteriores sem a aplicação o levar novamente ao fim.

Na conversão e na reauditoria, a percentagem conta documentos já processados.
Na recolha, conta os registos do índice indicado; na organização, apresenta
separadamente a conferência do catálogo e a aplicação dos nomes. A contagem
e a estimativa recomeçam ao mudar de fase, mantendo o tempo total decorrido.
O PDF que ainda está em curso não recebe uma percentagem inventada. O tempo
decorrido é atualizado enquanto o programa trabalha; o tempo restante é uma
estimativa calculada depois do primeiro documento e pode variar com o tamanho
dos PDFs, o OCR e os controlos de qualidade. Num único PDF, a estimativa pode
permanecer «a calcular» até terminar. As operações sem contagem disponível mantêm
o indicador de atividade e o tempo decorrido.

## Se alguma coisa falhar

A mensagem explica o próximo passo. Prima **Guardar relatório para o apoio**,
escolha onde guardar o ZIP e entregue-o ao apoio informático. O relatório contém
versão, erro técnico e registos da operação; pode conter caminhos e nomes dos
documentos. Não inclui os PDFs. Não precisa de ler tracebacks nem alterar
ficheiros do programa. Se `L:` não estiver disponível, confirme no Explorador
que consegue abrir a pasta ou escolha uma origem local.
No instalador, o mesmo botão guarda um relatório TXT da instalação.

## Avisos de segurança e rede

O Windows pode apresentar uma verificação de segurança ou reputação do
SmartScreen/Defender ao descarregar ou executar o instalador e os seus
componentes. A consulta cloud desse mecanismo pertence ao Windows. O instalador
CRL já contém Python, bibliotecas e modelos e não executa pip na estação.
O candidato atual não tem assinatura digital do editor; a adoção institucional
precisa da assinatura/validação de distribuição que o CRL aprove. A assinatura
também não garante a ausência de todos os avisos de reputação.

Se uma política impedir a execução, entregue a mensagem e o relatório ao apoio.
Não é necessário alterar as proteções do Windows para preparar os modelos.
Na conversão instalada, o processo local bloqueia ligações de rede feitas pelas
bibliotecas Python; a recolha de PDFs do BTE é uma operação separada que usa
Internet e está identificada como tal na interface. Ficheiros em pastas de
OneDrive/SharePoint podem precisar de estar disponíveis localmente antes do ensaio
sem Internet.

Referência: [reputação SmartScreen para aplicações Windows](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

Uma atualização é feita pelo instalador oficial da nova versão. As pastas de
dados e a configuração pessoal são conservadas. Nunca substituir scripts
isolados ou utilizar um ZIP de branch como atualização normal.

## Estado da distribuição

A linha 0.4.0rc3 é candidata e está sujeita a construção e validação. O estado
da construção está no [PR do candidato](https://github.com/calvicius-af/crl-pdf-markdown/pull/20).
Só uma versão com a ficha de aceitação preenchida deve ser entregue
como distribuição oficial. O instalador instala para o utilizador atual e não
pede privilégios de administrador; isso não confirma as permissões ou políticas
efetivas de uma estação CRL.
