# Preparar os documentos e resolver problemas

## Utilização normal

1. Abra o lançador CRL instalado. Clique em **Criar / usar pasta RNC…** e escolha
   a pasta `RNC_Dados_2026` (ou a do ano em análise).
2. Coloque os índices recebidos em `1_fontes/indices_bte` e clique em
   **Recolher PDFs (usa internet)**. As pastas ficam preenchidas; os originais vão
   para `1_fontes/irct/convencoes/PRI`, `SPE` ou `APU`.
3. Mantenha os modelos locais/offline. Ative OCR apenas para digitalizações.
4. Clique em **Construir Markdown** e aguarde. Docling pode demorar; não feche
   a janela durante a extração.
5. Clique em **Abrir relatório do lote**. Comece pelos documentos «Bloqueado»
   e «Falhou». «Sem alertas automáticos» também exige a revisão prevista no método.
6. Clique em **Conferir / aprovar…**. Abra PDF, Markdown e evidências. Registe
   o seu nome, o âmbito efetivamente conferido e a resolução dos avisos.
   Documentos bloqueados não podem ser aprovados.
7. Clique em **Entregar aprovados…** e escolha `3_analise/corpus_aprovado`.
   É criada uma nova entrega com `documentos/`, `conformidade.md` e
   `conformidade.json`. Só entram aprovações integrais com hashes atuais.
8. Importe os ficheiros de `documentos/` no MAXQDA. Conserve o relatório junto
   da entrega e registe a versão e o resultado da importação.

Se o texto mudar durante ou depois da conferência, a aprovação é recusada ou
invalida-se. Correções manuais devem ser guardadas separadamente em
`3_analise/revisao_textual`; o ciclo de nova auditoria dessas correções ainda está
em desenvolvimento. Não altere o JSON da auditoria para desbloquear um documento.

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
| Outra família documental               | A entrada continua no registo; a nomeação PE/AA exige os metadados de base ainda pendentes.   |
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
