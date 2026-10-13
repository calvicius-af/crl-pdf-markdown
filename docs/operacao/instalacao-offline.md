# Instalar e reparar sem internet

## Para quem vai utilizar

1. Receba uma pasta completa do pacote CRL, preparada para o seu sistema e Python.
   Não copie apenas um ficheiro ZIP interno ou só o lançador.
2. No Windows, faça duplo clique em `Instalar_CRL.bat`. O Python 3.13 com Tcl/Tk
   deve ter sido instalado pelo apoio informático. Não são necessárias permissões
   de administrador para instalar esta aplicação.
3. Espere pela mensagem «Instalação concluída». Não feche a janela enquanto trabalha.
4. A janela indica o caminho de `Abrir_CRL.bat`, normalmente dentro de
   `%LOCALAPPDATA%\CRL-PDF-Markdown`. Faça duplo clique nesse ficheiro.
5. A pasta de modelos e a opção offline ficam pré-preenchidas. Teste um PDF pequeno
   e abra o relatório antes de preparar um lote inteiro.

A aplicação fica instalada localmente, mesmo que o pacote tenha vindo de uma
unidade de rede. Reinstalar cria outro ambiente e conserva o anterior, as fontes
e as revisões. O lançador passa a usar a instalação concluída mais recente.

No macOS/Linux, o apoio executa `python3 instalar_offline.py` na pasta do pacote,
com a mesma versão de Python usada na preparação; no macOS, abre-se depois
`Abrir_CRL.command`. A validação de Windows continua necessária antes da distribuição.

## Se a instalação falhar

| O que aparece                                | O que fazer                                                                               |
| -------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Python não foi encontrado                    | Entregue a mensagem ao apoio informático. Peça Python 3.13, 64 bits, com Tcl/Tk.          |
| Pacote para outro sistema/Python             | Peça o pacote correto para essa estação; não tente misturar pastas de dois pacotes.       |
| Ficheiro em falta ou alterado                | Copie novamente o pacote completo e repita a instalação.                                  |
| Sem permissão ou espaço                      | Peça ao apoio que confirme espaço e acesso à pasta local do utilizador.                   |
| Instalação terminou, mas o programa não abre | Execute novamente o instalador e conserve os relatórios da pasta `assistencia`.           |
| Falta de modelos ou conversão muito lenta    | Confira a pasta `modelos`; teste um só PDF. Docling é mantido como extrator predominante. |

As falhas após o Python arrancar ficam em `assistencia`, sob a instalação local:
um Markdown com instruções e um TXT com o detalhe técnico. Se essa pasta não puder
ser escrita, é usada uma pasta temporária e o caminho é apresentado na janela.
Falhas anteriores ao arranque do Python só podem aparecer no lançador: conserve
o texto da janela. Não é necessário contactar o autor; o apoio recebe a evidência.

## Para o apoio: preparar o pacote uma vez

Prepare num computador com rede, com **o mesmo sistema, arquitetura e versão menor
de Python da estação**. Para Windows 3.13, prepare em Windows 64 bits com Python 3.13.
Não reutilize um pacote macOS para Windows. Conserve as versões fixadas em
`requirements/runtime.txt` e uma pasta completa de modelos Docling previamente
testada, incluindo OCR se essa função for necessária.

```powershell
py -3.13 scripts\preparar_offline.py --saida C:\CRL-pacote --modelos C:\modelos-docling
```

O preparador cria wheelhouse, modelos, vocabulários, guias, instalador e manifesto
de integridade. O instalador verifica hashes e compatibilidade antes de criar o
ambiente. Usa pip com `--no-index`, sem compilar bibliotecas na estação e sem rede.
A preparação precisa de rede; **não foi executada nesta intervenção**.

Se a preparação falhar, a pasta fica marcada `PACOTE_INCOMPLETO.txt` e não pode
ser distribuída. Volte a preparar numa pasta nova após resolver a causa.

## Gate obrigatório antes de distribuir

- Instalar a partir de uma cópia do pacote com rede desligada, sem privilégios admin.
- Testar caminhos com espaços, unidade de rede e pacote só de leitura.
- Abrir a interface pelo lançador e converter um PDF com tabela.
- Confirmar que os modelos não provocam downloads e que o relatório é legível.
- Executar `doctor` e conferir erros de pacote, modelos ausentes e permissões.
- Registar máquina, Python, app, Docling, modelos, hashes e resultado em
  `docs/validacao/`. Estes testes de estação ainda estão pendentes.

O comando `doctor` verifica imports, Python, integridade do manifesto, perfil de
modelos e correspondência da versão Docling. Regista se os ficheiros OCR foram
verificados. Não executa uma conversão nem demonstra fidelidade de um documento.

## O que o pacote e o ensaio verificam

O pacote usa formato `schema: 2` em `pacote.json`. A pasta deve ser conservada
inteira, sem juntar ficheiros de outros pacotes. O manifesto inclui os hashes,
o sistema, a arquitetura, o Python, as versões de todas as wheels e o perfil OCR.
`requirements.install.txt` fixa cada dependência transitiva e o hash da sua wheel.
O instalador recusa versões antigas do formato, ligações simbólicas, caminhos
fora do pacote, modelos sem manifesto e ficheiros alterados ou não inventariados.
O manifesto comprova integridade relativamente à cópia preparada; a equipa deve
receber o pacote por uma origem de confiança.

Os modelos são conferidos pelo `manifesto_modelos.json`, pelo perfil exigido
pelo pipeline e pela versão de Docling. Um `.safetensors` isolado não basta.
Se foram incluídos modelos OCR completos, o ensaio ativa o RapidOCR português
fixado pela aplicação e força a leitura da página para carregar os seus modelos.
Se o pacote não contém OCR, o ensaio só demonstra o percurso sem OCR.

Antes de publicar o lançador, o instalador copia recursos para a pasta local,
instala apenas wheels com hashes, executa `pip check` e converte um PDF sintético
com tabela. Usa explicitamente os modelos copiados e bloqueia sockets no processo
de ensaio. Exige conversão concluída e preservação do título e dos valores do PDF.
Não usa documentos do corpus para preparar ou testar a instalação.

Uma falha em dependências, modelos, ensaio ou publicação conserva o lançador
anterior. As novas pastas podem ficar guardadas para investigação; o apoio deve
confirmar a instalação referida por `instalacao.json` antes de limpar pastas
antigas. Não apagar a pasta `assistencia` antes de guardar o relatório necessário.
Uma segunda instalação simultânea é recusada. Se a janela foi fechada à força,
o apoio deve confirmar que não existe um instalador em execução e só então remover
a pasta vazia `.instalacao-em-curso` para repetir.

O apoio pode escolher outra pasta **local** com
`python instalar_offline.py --destination "CAMINHO LOCAL"`. No pacote Windows,
`Instalar_CRL.bat` usa a versão menor de Python registada na preparação e aceita
origens UNC através de `pushd`. O lançador da aplicação usa o Python do ambiente
local concluído.

O workflow manual `offline.yml` prepara e instala um pacote real em Windows 3.13,
com caminhos com espaços, pacote sem permissão de escrita e ensaio com OCR e
sockets bloqueados. Guarda logs, manifesto e versões, sem as wheels/modelos.
Uma execução concluída não substitui o ensaio na estação do CRL, em partilha
UNC/unidade mapeada e por uma pessoa que não seja o autor. Esses gates continuam
pendentes até existir o respetivo registo.

Para pedir apoio, entregue apenas os relatórios da operação falhada. Não acrescente
PDF, corpus, ficheiros pessoais nem dumps de variáveis de ambiente. Os relatórios
da aplicação retiram credenciais explícitas de URLs e campos de segredo; reveja
sempre os ficheiros antes de os partilhar fora da equipa.
