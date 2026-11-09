# Distribuição Windows completa

## Responsabilidades

Quem prepara a distribuição resolve as wheels, prepara os modelos e monta o
runtime. A colega recebe um único EXE e usa a interface. Os scripts antigos
`preparar_offline.py` e `instalar_offline.py` são ferramentas técnicas e não
constituem o procedimento normal de instalação da linha 0.4.

## Construção

Executar o workflow **Instalador Windows completo** num Windows x64 com CPython
3.13 completo (incluindo Tcl/Tk), Inno Setup 6 e acesso à rede. Também corre em
PRs que alteram o produto. O workflow:

1. Usa as constraints de runtime e transitivas Windows já fixadas no projeto.
2. Prepara modelos com manifesto e wheels com hashes usando `preparar_offline.py`.
3. Usa `montar_windows.py` para copiar o runtime completo do construtor, instalar
   as wheels nele e juntar modelos, recursos e licenças. Não usa um venv
   deslocável nem depende do Python instalado no computador de destino.
4. Muda a pasta do runtime, verifica os hashes e versões, abre Tcl/Tk e converte
   o PDF sintético com texto e OCR em processos isolados, com sockets bloqueados
   no processo principal e nos trabalhadores. Usa `L:` criado com `subst`.
5. Compila `packaging/windows/CRL.iss` e ensaia a instalação do EXE e a conversão.

O ensaio CI não representa um Windows limpo nem um utilizador normal do CRL.
`subst L:` também não prova permissões numa partilha real. O gate humano abaixo
continua obrigatório. A construção falha se o conteúdo exceder o limite de um
único EXE do Inno Setup; não aceita partes `.bin` externas.

O runtime contém `python313._pth` com caminhos relativos, sem consulta ao PATH
ou ao registo para bibliotecas. O atalho usa `pythonw.exe -I -X utf8 -B` e os
modelos incluídos. Caches e configuração ficam em `%LOCALAPPDATA%\CRL-PDF-Markdown`.
A instalação por versão conserva a anterior, mas o atalho passa para a nova.
Não executar instaladores de versões anteriores como procedimento de atualização.
Uma unidade sem alias 8.3 para caminhos com acentos pode exigir que o apoio
escolha uma pasta local sem acentos; testar explicitamente na estação.

## Aceitação obrigatória na estação

Preencher uma ficha por candidato com versão, commit, SHA-256 do EXE, Windows,
arquitetura, identificação da estação e conta normal usada. Não incluir
palavras-passe. Antes do teste, confirmar ausência de Python e desligar a rede
externa. Para testar `L:` real, manter apenas o acesso à partilha interna ou
usar uma segunda fase do ensaio; registar as condições sem chamar «sem rede»
a uma ligação externa ativa.

- [ ] Duplo clique no EXE abre a instalação sem pedir credenciais de administrador.
- [ ] Escolha de pasta, progresso, cancelamento e instalação funcionam.
- [ ] O atalho **Abrir CRL** abre sem consola, sem comandos e sem Python externo.
- [ ] A primeira janela guarda as cinco pastas; fechar/reabrir conserva-as.
- [ ] Um PDF sintético local produz Markdown legível com título e valores corretos.
- [ ] Uma digitalização funciona com OCR, com a rede externa desligada.
- [ ] Um PDF em `L:` real funciona com conta normal e permissões de leitura.
- [ ] Falta de acesso a `L:` e saída sem escrita dão mensagens compreensíveis.
- [ ] **Guardar relatório para o apoio** gera um ZIP com o detalhe técnico.
- [ ] Caminhos com espaços/acentos, reinício e segunda abertura funcionam.
- [ ] Atualização por instalador conserva dados, configuração e saídas existentes.
- [ ] A colega conclui a conversão sozinha, sem editar ficheiros do programa.

O resultado deve indicar **aprovado** ou **reprovado**, com falhas observadas.
Ensaios anteriores da conversão não dispensam este ensaio do instalador.

## Publicação oficial

Só depois da aceitação, atribuir a versão final em `pyproject.toml` e
`src/crl_markdown/__init__.py`, construir novamente e repetir a aceitação do
EXE final (a evidência pertence ao seu hash). Publicar uma release numerada
com o EXE, SHA256SUMS, notas e ficha de aceitação. Manter os candidatos como
pré-releases. A publicação ainda não é automática: nenhum sucesso CI promove
um candidato a versão aprovada. A preparação deve conservar as licenças das
wheels e dos modelos e confirmar a sua redistribuição antes de publicar.

Referências técnicas: [runtime Python no Windows](https://docs.python.org/3.13/using/windows.html),
[privilégios do Inno Setup](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm)
e [limite do instalador único](https://jrsoftware.org/ishelp/topic_setup_diskspanning.htm).
