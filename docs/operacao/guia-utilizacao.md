# Preparar os documentos e resolver problemas

## Utilização normal

1. Abra o lançador CRL instalado. Clique em **Criar / usar pasta RNC…** e escolha
   a pasta `RNC_Dados_2026` (ou a do ano em análise).
2. Coloque os índices recebidos em `1_fontes/indices_bte` e clique em
   **Recolher PDFs (usa internet)**. As pastas ficam preenchidas; os originais vão
   para `1_fontes/irct/convencoes/PRI`, `SPE` ou `APU`.
   Portarias, adesões e acórdãos são organizados nas respetivas pastas de IRCT.
   Se os PDFs já foram recolhidos, clique em **Organizar PDFs (sem rede)** para
   repetir a nomeação com as regras atuais, conservando originais e nomes já
   atribuídos. O resultado e eventuais conflitos constam de
   `0_gestao/catalogo/nomeacao.csv`; o catálogo anual conserva as fontes dos dados.
3. Mantenha os modelos locais/offline. Ative OCR apenas para digitalizações.
   Em **Documentos a converter na pasta RNC**, escolha a família ou **Todos os
   documentos IRCT**. As alterações/deliberações ACEP e ACCE fazem parte das
   convenções APU; as cessações têm seleção própria. O catálogo de relações
   indica se as publicações de base foram encontradas ou estão fora do lote.
4. Clique em **Construir Markdown** e aguarde. Docling pode demorar; não feche
   a janela durante a extração.
5. Clique em **Abrir relatório do lote**. Comece pelos documentos «Bloqueado»
   e «Falhou». «Sem alertas automáticos» também exige a revisão prevista no método.
6. Clique em **Conferir / aprovar…**. Abra PDF, Markdown e evidências. Registe
   o seu nome, o âmbito efetivamente conferido e a resolução dos avisos.
   Documentos bloqueados não podem ser aprovados.
   Este botão só funciona depois da conversão; não revê a nomeação dos PDFs.
7. Clique em **Entregar aprovados…** e escolha `3_analise/corpus_aprovado`.
   É criada uma nova entrega com `documentos/`, `conformidade.md` e
   `conformidade.json`. Só entram aprovações integrais com hashes atuais.
8. Importe os ficheiros de `documentos/` no MAXQDA. Conserve o relatório junto
   da entrega e registe a versão e o resultado da importação.

Se o texto ou a auditoria mudar, é necessária uma decisão sobre a versão atual.
Não altere o JSON nem o Markdown final para desbloquear o documento: use o editor
de correções, que conserva o original e cria uma publicação auditada separada.

## Corrigir, reauditar e decidir na GUI

1. Para aplicar regras atualizadas a uma conversão existente, selecione a sua
   **Pasta de saída** e clique em **Reauditar lote (sem nova extração)**.
   A operação verifica a cache e cria uma pasta nova. O campo de saída passa a
   apontar para essa nova corrida quando termina; a anterior fica conservada.
2. Abra **Conferir / aprovar…**. Filtre por estado, família ou regra e selecione
   o documento. A lista mostra as ocorrências, IDs e páginas disponíveis.
   **Relatório deste documento** abre as evidências da versão selecionada.
3. Preencha o responsável. Se há erro real, escolha **Criar / editar correção**.
   Edite no rascunho separado, guarde e clique em **Reauditar correção guardada**.
   O editor tem deslocação horizontal para tabelas largas.
4. Depois da auditoria, confira o resultado com o PDF. A caixa de conferência
   integral é reposta; uma correção não concede aprovação automaticamente.
5. Para registar uma resolução, selecione a ocorrência, indique a página e as
   evidências nas notas e use a ação adequada: **conferido** para avisos,
   **corrigido** para uma grelha efetivamente alterada, **decorativo** para uma
   figura sem conteúdo a transcrever ou **transcrito** quando a transcrição foi
   incorporada e conferida. Clique em **Resolver ocorrência e reauditar**.
   Montantes, completude e falhas de referência não podem ser dispensados por nota.
6. Se faltar reconhecimento de conteúdo numa imagem, use **Reler páginas com
   OCR** e indique as páginas e a pasta de modelos locais. Só essas páginas são
   reextraídas; as restantes são verificadas e reutilizadas. Se um elemento
   atravessar a seleção, inclua todas as suas páginas. Uma edição humana ativa
   exige reconciliação e não é substituída automaticamente pelo OCR.
7. Registe a decisão sobre a versão atual. A aprovação fica desativada enquanto
   houver erros por resolver. A rejeição continua disponível. **Entregar aprovados**
   utiliza a revisão ativa aprovada, preservando o nome relativo do documento.

As correções ficam em `_auditoria/correcoes`, com publicações imutáveis e
referência para a versão ativa em `_auditoria/versoes`. O relatório do lote é o
retrato da corrida original; cada correção tem a sua auditoria. A janela de
conferência e a entrega verificam a versão ativa e os seus hashes.

Consulte a [hierarquia Markdown](hierarquia-markdown.md) e os
[perfis de auditoria](../../src/crl_markdown/vocabularios/perfis_auditoria.md).

Não selecione «Substituir saídas existentes» se houver correções humanas nessa
pasta. Prefira uma saída nova por lote. Uma cache Docling verificada permite
reaplicar regras mais depressa, mas uma nova extração é necessária quando o erro
está no reconhecimento dos itens.

## Retomar trabalho anterior e transferir uma revisão

A conferência e a entrega consultam os documentos do histórico da pasta de saída,
incluindo as corridas anteriores em `_auditoria/corridas`. Converter um documento
isolado na mesma pasta não deve retirar os documentos anteriores da conferência.
O relatório do último lote continua a representar apenas essa execução.
Ao reabrir a aplicação, é retomada a última pasta de revisão desse projeto.
**Lotes recentes…** dá acesso às pastas anteriores e à principal configurada,
sem alterar a configuração das cinco pastas nem apagar resultados indisponíveis.
Se a última tentativa de um documento falhou, a conferência pode apresentar a
versão anterior, identificada como tal, desde que a sua integridade seja válida.

Para voltar a uma pasta usada anteriormente, clique em **Retomar revisão noutra
pasta…** e escolha a pasta Markdown que contém `_auditoria`. Não escolha uma
subpasta de `corridas`: os respetivos manifestos referem-se aos artefactos da
pasta de saída original.

Para procurar trabalho que deixou de aparecer numa versão anterior:

1. Na máquina onde trabalhou, conserve a pasta original e faça uma cópia completa
   da saída Markdown, incluindo a pasta `_auditoria` e todas as suas subpastas.
2. Em `_auditoria/corridas/*/manifest.json` ficam os índices das corridas
   anteriores. Os relatórios `documentos/*.qualidade.json` guardam as ocorrências;
   `correcoes` guarda os rascunhos/publicações, `versoes` as referências ativas e
   `revisoes` as decisões humanas. Algumas subpastas só existem se foram usadas.
3. Copie também os PDFs originais, caso estejam noutra localização. Não altere
   ficheiros JSON para corrigir caminhos nem reconverta sobre a única cópia.
4. Na máquina de destino, abra a cópia por **Retomar revisão noutra pasta…**.
   Se os originais não forem encontrados, escolha a saída no campo respetivo e
   use **Localizar PDFs do lote…**, indicando a pasta com os PDFs copiados.
5. A associação confirma o conteúdo por SHA-256 e guarda referências locais por
   máquina. Reabra a conferência. Os relatórios e as aprovações anteriores não
   são reescritos para alterar os caminhos.

Ao fechar um editor ou a janela de conferência/aplicação, as alterações por guardar
pedem Guardar, Descartar ou Cancelar. Guardar uma correção ou notas não equivale
a aprovar o documento. Notas recuperadas não assinalam conferência integral.
Para retomar uma correção ainda não publicada, indique o mesmo responsável e
use **Criar / editar correção**; a aplicação oferece o rascunho da mesma base.

Uma gravação de rascunho recusa alterações concorrentes que detete, conservando
o texto no editor. Copie esse texto antes de fechar para reconciliar as versões.
Uma nova extração com substituição é recusada quando o documento tem correções
ou decisões humanas; use uma saída nova.

## Rever em máquinas diferentes e incorporar o trabalho

Conserve uma pasta principal do corpus. Na conferência dessa pasta:

1. Indique o responsável e use **Preparar cópia para outra pessoa…**. Guarde as
   edições antes de continuar. É criada uma pasta nova com os documentos,
   auditorias, correções, decisões e PDFs verificados. Entregue a pasta completa;
   não é preciso instalar modelos para conferir ou editar texto já extraído.
2. A outra pessoa abre a cópia por **Retomar revisão noutra pasta…**, identifica-se
   no campo de responsável e trabalha normalmente. A recuperação de notas mostra
   o autor anterior, mas não atribui esse nome à pessoa que abre a aplicação.
3. Para distribuir trabalho em paralelo, atribua documentos diferentes a cada
   pessoa. As cópias podem partir da mesma base. Não substitua a pasta principal
   por uma das cópias nem use o Explorador para sobrepor ficheiros de duas revisões.
4. Depois de fechar a aplicação na máquina de revisão, devolva a pasta completa.
   Na pasta principal, use **Importar revisão recebida…**. As alterações são
   comparadas com a base de onde a cópia partiu, conservando autoria e histórico.
5. Alterações em documentos diferentes podem ser incorporadas. Revisões
   incompatíveis do mesmo documento são recusadas; conserve ambas as pastas,
   compare os textos e crie uma nova correção na principal com a reconciliação
   descrita nas notas. Não escolha uma versão apenas pela data do ficheiro.

Uma cópia de revisão destina-se à conferência, correção e OCR dirigido. Se for
usada para uma nova conversão que substitua o corpus base, a importação é recusada.
Uma atualização das regras na pasta principal pode exigir nova cópia de revisão.
Os modelos para OCR dirigido têm de ser selecionados na máquina que o executa;
o pacote de revisão não inclui modelos nem Python.

As decisões têm uma cadeia de proveniência. Uma decisão registada depois de
abrir a conferência exige reabrir o documento antes de registar outro parecer.
Se uma sobreposição manual/sincronização originar dois ramos de decisão, a entrega
é bloqueada. **Reconciliar decisões…** permite uma nova decisão identificada,
com notas e conferência da versão atual, conservando os pareceres anteriores.

A importação conserva um registo e os ficheiros anteriores. Uma falha tratável
repõe as alterações aplicadas. Se houver interrupção do processo, use **Recuperar
importação interrompida…** na janela principal, com a pasta de saída selecionada.
A recuperação recusa-se a substituir alterações posteriores que detete.

Este mecanismo não depende de escrita simultânea numa partilha. Uma pasta
sincronizada não garante bloqueios entre computadores; use as cópias de revisão
e a importação explícita. O comportamento de partilhas Windows reais continua
a precisar de ensaio na infraestrutura do CRL.

## Histórico das ocorrências

**Histórico de ocorrências…** conserva as observações por versão, mesmo quando
uma regra deixa de emitir o alerta. As situações são distintas:

- **Pendente:** o alerta existe na versão atual.
- **Resolvida por conferência humana:** há uma resolução registada para a versão.
- **Ausente na versão atual — por confirmar:** a reauditoria deixou de emitir o
  alerta; isto não o dá automaticamente como resolvido.
- **Fonte alterada — exige nova conferência:** o PDF mudou, invalidando a
  confirmação anterior para essa fonte.
- **Versão atual por verificar:** faltam originais ou há uma falha de integridade;
  o histórico continua visível, mas não pode ser confirmado como atual.

Para uma ocorrência ausente, **Confirmar resolução histórica…** exige responsável
e evidência da conferência atual. Não permite dispensar um erro que continue na
auditoria atual. Uma alteração posterior da versão exige reconfirmação.
Na reauditoria para uma pasta nova, o histórico é transportado e as evidências
humanas anteriores ficam separadas; não se ativam aprovações antigas automaticamente.

A reauditoria pela GUI considera o inventário histórico. Na CLI, acrescente
`--history` para selecionar também documentos de corridas anteriores. A opção
`--dry-run` conserva a simulação e a proveniência da seleção.

## Reauditar uma seleção pela linha de comandos

Para investigar um padrão sem repetir o lote inteiro, selecione os documentos
pelas ocorrências e estados da corrida anterior. Comece por simular:

```powershell
.venv\Scripts\python.exe -m crl_markdown reaudit --out results\anterior --family convencoes --rule AMOUNTS --status blocked --dry-run
.venv\Scripts\python.exe -m crl_markdown reaudit --out results\anterior --destination results\montantes --family convencoes --rule AMOUNTS --status blocked
```

No macOS/Linux, use `.venv/bin/python` e caminhos com `/`.

- `--family`: primeira subpasta do caminho relativo no manifesto, como
  `convencoes`, `portarias_extensao` ou `acordaos`. Use `.` para PDFs na raiz.
  O filtro de pasta não reclassifica a tipologia nem o âmbito documental.
- `--rule`: código exato de uma regra presente no manifesto, como `AMOUNTS`
  ou `TABLE_OVERLAP`.
- `--status`: estado automático `passed`, `review` ou `blocked`.
- `--document`: caminho relativo exato de um PDF, incluindo as subpastas.
- `--dry-run`: apresenta JSON com critérios, documentos selecionados, corrida
  e hash do manifesto de origem; não lê a cache/PDF nem escreve resultados.

Repita uma opção para aceitar qualquer dos seus valores: `--rule AMOUNTS
--rule TABLE_OVERLAP`. Opções diferentes cruzam-se: família **e** regra **e**
estado **e**, quando indicado, documento. Um valor desconhecido ou uma seleção
vazia dá erro antes de criar a pasta de destino. Documentos sem extração completa
não podem ser reauditados; use o filtro de estado para selecionar os já convertidos.

A reutilização exige que os hashes do PDF e da extração coincidam com o manifesto
selecionado e com a cache. Uma cache substituída ou sem essa identidade falha
nesse documento, mesmo quando o seu relatório individual é internamente consistente.

A seleção usa o retrato registado da corrida anterior, sem incorporar decisões
ou correções humanas posteriores. Todos os controlos atuais são aplicados aos
documentos selecionados, mesmo que uma regra usada no filtro tenha deixado de
produzir ocorrências. A operação reaplica as regras à extração Docling guardada;
para trabalhar sobre uma correção humana, use **Reauditar correção guardada**.

O manifesto e os relatórios da nova corrida conservam a proveniência, os filtros
e a dimensão da seleção. Uma corrida parcial não representa o corpus inteiro e
não aprova os documentos. Os originais e as decisões anteriores são conservados.
A GUI mantém o comando de reauditoria do lote completo; estes filtros de execução
estão disponíveis na CLI.

## Recolha e nomeação: preparação inicial pelo apoio

Os comandos abaixo funcionam a partir da raiz da aplicação ou da pasta de recursos
instalada. No Windows, o apoio usa o Python cujo caminho consta de `instalacao.json`;
os exemplos usam um `.venv` de desenvolvimento. O registo identifica cada download.

```powershell
.venv\Scripts\python.exe -m crl_markdown init C:\Dados\RNC_Dados_2026
.venv\Scripts\python.exe -m crl_markdown collect --workspace C:\Dados\RNC_Dados_2026
.venv\Scripts\python.exe -m crl_markdown collect --workspace C:\Dados\RNC_Dados_2026 --confirmar-rede
.venv\Scripts\python.exe -m crl_markdown name --workspace C:\Dados\RNC_Dados_2026
.venv\Scripts\python.exe -m crl_markdown name --workspace C:\Dados\RNC_Dados_2026 --aplicar
.venv\Scripts\python.exe -m crl_markdown convert --workspace C:\Dados\RNC_Dados_2026 --models C:\modelos-docling --offline
```

Depois de `init`, copie apenas os índices BTE para `1_fontes/indices_bte`;
o export de organizações fica em `1_fontes/externas`. Não ponha esse export na
pasta de índices: é um registo diferente e a recolha avisará que não o reconhece.
Simular não descarrega; descarregar exige `--confirmar-rede`. `name` simula;
`name --aplicar` copia. Consulte `0_gestao/catalogo/nomeacao.csv` para pendências.

Para utilizar siglas corrigidas na pasta RNC, acrescente
`--siglas C:\Dados\RNC_Dados_2026\0_gestao\vocabularios\siglas.csv` ao comando `name`.
Pode também indicar `--ambitos` para o vocabulário confirmado da equipa.

## Ler o relatório e agir

| Situação                               | Próximo passo                                                                                 |
| -------------------------------------- | --------------------------------------------------------------------------------------------- |
| Falhou                                 | Leia «O que fazer» no relatório; confirme ficheiro, modelos, acesso e instalação.             |
| Bloqueado                              | Abra o PDF original e confira as passagens/tabelas indicadas; não aprove esse texto ainda.    |
| Rever                                  | Confira as páginas e os avisos. Registe o resultado mesmo quando o aviso for falso positivo.  |
| Sem alertas automáticos                | Aplique a amostragem/revisão definida no método; não equivale a aprovação humana.             |
| Sigla por confirmar                    | O apoio verifica o nome no CSV, confirma a fonte e regista a decisão antes de repetir `name`. |
| Outra família documental               | Escolha a família na GUI; consulte o catálogo para a classificação e as relações com a base.  |
| PDF antigo aparece depois de uma falha | Consulte o manifesto da tentativa atual; não use o resultado antigo como se fosse novo.       |

Se o problema continuar, entregue ao apoio informático o relatório resumido,
`manifest.json`, o ficheiro de falha JSON/TXT quando existir e o nome do PDF.
Os relatórios contêm caminhos e excertos documentais: partilhe-os pelo canal de
apoio definido pela organização. O apoio deve reproduzir com um documento e
registar a correção como teste de regressão.

Para verificar o ambiente sem descarregar:

```powershell
.venv\Scripts\python.exe -m crl_markdown doctor --models C:\modelos-docling --out C:\Dados\assistencia
```
