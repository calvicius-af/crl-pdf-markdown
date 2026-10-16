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
