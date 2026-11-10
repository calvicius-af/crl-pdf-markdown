# Preparação da primeira release — revisão de 10/11/2026

Âmbito: código e documentação locais da versão `0.4.0rc2`. Esta revisão não
constitui aceitação do instalador Windows, nova extração do corpus real ou
validação da importação no MAXQDA. As propostas abaixo não estão implementadas.

## Parecer

O percurso funcional já cobre preparação, conversão, controlo de qualidade,
correção, aprovação e entrega. A primeira release beneficia sobretudo de fechar
o ciclo de utilização: instalar, aprender, trabalhar, recuperar, atualizar e
desinstalar. Acrescentar mais capacidades de análise tem menor prioridade.

Desinstalação, atualização e manual fazem sentido. Existem bases para os três,
mas ainda não um percurso completo e ensaiado para o utilizador final.

## Funcionalidades atuais e limites

| Área         | O que existe                                                                                              | Limite relevante para a release                                                                                       |
| ------------ | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Instalação   | EXE offline previsto, Python/Tk, bibliotecas, modelos e PDF de teste incluídos; instalação por utilizador | A aceitação numa estação CRL continua pendente; CI não representa um Windows limpo                                    |
| Configuração | Cinco pastas persistentes, separação entre programa e dados, suporte a unidade mapeada                    | Alterar pastas não migra dados; falta um procedimento de restauro com caminhos diferentes                             |
| Recolha      | Índices Excel, descarga do BTE, catálogo e integridade por hash                                           | Exige índices fornecidos; não descobre novos boletins automaticamente                                                 |
| Organização  | Famílias, nomes RNC estáveis, siglas, relações e pendências                                               | As confirmações de vocabulários ainda dependem de ficheiros e apoio técnico                                           |
| Conversão    | PDF individual ou lote, subpastas, OCR opcional e modelos locais                                          | Tabelas complexas, imagens e fórmulas podem exigir correção humana                                                    |
| Robustez     | Processos isolados, repetição após queda nativa, timeout e reutilização de resultados verificados         | Falta uma ação de paragem controlada na conversão; fechar a aplicação interrompe o trabalho                           |
| Qualidade    | Completude, montantes, símbolos, tabelas e relatórios por documento/lote                                  | Ausência de alertas não prova fidelidade ao PDF                                                                       |
| Revisão      | Ocorrências, correções versionadas, reauditoria e OCR dirigido                                            | Editor precisa de proteção contra alterações não guardadas; interface de conferência exige janela mínima de 950 × 700 |
| Entrega      | Só aprovações integrais atuais, hashes e relatório metodológico                                           | A importação direta de Markdown no MAXQDA permanece um ensaio de aceitação                                            |
| Apoio        | Mensagens orientadas à recuperação, ZIP de assistência e diagnóstico por CLI                              | Diagnóstico técnico não tem botão próprio; relatórios podem conter caminhos e excertos documentais                    |

## Achados prioritários

### 1. [P1] O catálogo pode perder alterações entre duas instâncias

`Registo.carregar()` lê o catálogo inteiro para memória e `Registo.guardar()`
reescreve-o por substituição atómica, sem bloqueio que cubra leitura, alteração
e gravação (`src/crl_markdown/recolha.py:346–377`). A recolha e a nomeação usam
este registo; `naming.py:260–272` também não estabelece exclusão mútua.

Se duas instâncias lerem o mesmo estado e gravarem alterações diferentes, a
última gravação pode eliminar as alterações da primeira. A escrita atómica
protege o ficheiro contra gravação parcial, mas não resolve esse conflito.
O indicador de operação em curso da GUI só protege uma janela da aplicação.

Proposta para a primeira release: bloqueio do catálogo durante a operação
completa e mensagem clara de pasta ocupada. Testar duas instâncias no mesmo
computador e, se houver escrita partilhada, duas contas numa partilha real.
Não assumir que um bloqueio local assegura exclusão entre cópias OneDrive.
Até esse ensaio, definir um único responsável por escrever em cada pasta RNC.

### 2. [P2] Atualização e remoção de versões antigas estão incompletas

O instalador mantém um `AppId` fixo, instala numa pasta por versão e reutiliza
os nomes dos atalhos (`packaging/windows/CRL.iss:12–45`). O diretório anterior
fica conservado, mas não há gestão explícita das versões antigas, retorno à
anterior, recusa de instalação de uma versão mais antiga ou migração de dados.

O Inno Setup inclui desinstalador por omissão. Portanto, não é necessário
construir um desinstalador separado. Contudo, o mesmo `AppId` determina a chave
de desinstalação no registo, enquanto cada pasta conserva os seus ficheiros de
desinstalação. Isto exige ensaio de duas versões: não se pode pressupor que o
Windows apresente e remova todas as versões como instalações independentes.

Proposta: manter atualização manual pelo EXE oficial na primeira release,
definir uma versão ativa e um procedimento de recuperação, e testar a remoção
sem perder dados ou deixar atalhos inválidos. A configuração pessoal e os dados
de investigação devem permanecer por omissão. Limpeza de caches/configuração,
se oferecida, deve ser uma ação distinta e explícita.

Também falta coordenação explícita entre aplicação e instalador para impedir
atualização/desinstalação durante uma operação. `CloseApplications=yes` procura
aplicações que usam ficheiros a atualizar; instalar noutra pasta não oferece
uma garantia equivalente. Um mutex de aplicação é uma opção a avaliar.

Fontes: [desinstalador por omissão](https://jrsoftware.org/ishelp/topic_setup_uninstallable.htm),
[identidade e chave de desinstalação](https://jrsoftware.org/ishelp/topic_setup_appid.htm),
[fecho de aplicações](https://jrsoftware.org/ishelp/topic_setup_closeapplications.htm)
e [mutex de aplicação](https://jrsoftware.org/ishelp/topic_setup_appmutex.htm).

### 3. [P2] Fechar o editor pode perder correções ainda não guardadas

O editor cria uma janela e guarda apenas por botão ou antes da reauditoria
(`src/crl_markdown/review_app.py:248–272`). Não regista um tratamento de fecho
nem verifica se o texto foi alterado.

Consequência: escrever uma correção e fechar no X pode perder esse trabalho,
embora as publicações já guardadas permaneçam protegidas.

Proposta: detetar alterações e oferecer Guardar, Descartar ou Cancelar ao fechar
o editor e a aplicação. Evitar abrir dois editores sobre o mesmo rascunho sem
controlo de conflito. A reauditoria deve usar uma cópia estável do texto guardado.

### 4. [P2] O manual completo não acompanha a instalação

Há um guia de utilização e um guia de instalação. O construtor copia apenas o
segundo como `LEIA-PRIMEIRO.md` (`scripts/montar_windows.py:79`); não inclui o
guia operacional completo nem existe uma ação Ajuda na janela principal.
O Markdown também depende de uma aplicação associada no Windows, e ligações
relativas do guia copiado deixam de corresponder à estrutura original.

Proposta: manual HTML local, com navegação e recursos incluídos, aberto por
Ajuda/F1 e acessível pelo menu Iniciar. Deve funcionar sem Internet e sem editor
Markdown. Gerá-lo a partir de uma única fonte, com versão e data, para evitar
divergência entre o manual instalado e a documentação do projeto.

### 5. [P2] A entrega pode bloquear a interface em pastas lentas

`deliver_approved()` executa `deliver()` diretamente no callback da GUI
(`src/crl_markdown/app.py:433–445`). A operação verifica documentos, calcula
hashes e copia ficheiros; numa partilha lenta, a janela pode deixar de responder.
O tempo necessário depende da dimensão do lote e do acesso aos ficheiros.

Proposta: executar a entrega numa thread de trabalho, com estado de operação e
progresso. Conservar a publicação por pasta temporária, a verificação de hashes
e a recusa de substituir uma entrega existente, que já são boas salvaguardas.

## As três propostas do utilizador

| Proposta      | Decisão recomendada para a primeira release                                   | Critério de aceitação                                                                            |
| ------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Desinstalador | Usar e completar a integração existente do Inno Setup                         | Remover pelo Windows; preservar dados, correções e decisões; tratar versões anteriores e atalhos |
| Atualização   | Instalação manual de versão oficial, com notas de alteração e compatibilidade | Atualizar de A para B; abrir lote antigo; conferir aprovações/correções; recuperar A se B falhar |
| Manual        | Incluir manual local acessível pela aplicação                                 | Uma colega sem acesso ao repositório conclui o percurso até à entrega consultando apenas a ajuda |

Não é necessária atualização automática nesta fase. Acrescentaria distribuição,
verificação da origem, rede, recuperação e políticas institucionais a um produto
cujo funcionamento principal é local. Pode ser estudada após estabilizar o
procedimento manual. A atualização não deve alterar silenciosamente o corpus
nem transformar aprovações antigas em novas aprovações.

O manual deve explicar: finalidade e limites; termos PDF/Markdown/OCR; o que a
aplicação faz em cada botão; primeiro documento; preparação por índices;
significado dos estados; correção e aprovação; entrega e importação no MAXQDA;
retoma após interrupção; atualização, desinstalação e cópias de segurança;
erros frequentes e contacto do apoio. Incluir um exemplo de tabela problemática
e explicar a diferença entre ter texto extraído e ter conteúdo conferido.

## Outros constrangimentos previsíveis

- **Carga de conferência:** o ensaio histórico de 29/10 registou 78 documentos
  a rever e 68 bloqueados em 324. É evidência da versão então ensaiada, não uma
  medição da 0.4. Um piloto deve medir tempo de conferência e correção; rapidez
  de conversão, por si só, não mede a utilidade operacional.
- **Memória, disco e duração:** runtime, modelos, caches e versões conservadas
  ocupam espaço. Medir numa estação representativa antes de publicar requisitos
  mínimos; não atribuir valores de RAM/disco sem evidência. Verificar escrita
  e espaço disponível antes de operações demoradas, sem prometer uma previsão
  exata do tamanho final.
- **Interrupção e recuperação:** acrescentar paragem controlada entre documentos,
  distinguindo-a da terminação imediata do documento atual. Explicar a retoma e
  o destino de resultados parciais. A proteção existente por hashes deve manter-se.
- **Cópias de segurança:** documentar e ensaiar cópia/restauro de todas as cinco
  pastas configuradas, das correções/decisões e da configuração pessoal, com a
  aplicação parada. Existem caminhos absolutos nos registos; mudar de computador
  pode exigir reconciliação. Sincronização não substitui restauro ensaiado.
- **Ecrãs e escala:** verificar a janela de conferência em portátil e com escala
  Windows de 125%/150%; o mínimo de 950 × 700 pode exceder a área útil. Priorizar
  ações acessíveis e deslocamento quando a altura não chegar.
- **Distribuição institucional:** fechar validação/assinatura aprovada pelo CRL,
  licenças incluídas, origem oficial do EXE, hash, notas e apoio responsável.
  Os documentos de distribuição já reconhecem estas pendências.

## Âmbito recomendado para fechar a primeira release

Antes de distribuição geral:

1. Corrigir o conflito de catálogo e a perda de edições não guardadas.
2. Ensaiar instalação, atualização e desinstalação de duas versões; definir
   conservação de dados e recuperação de uma atualização problemática.
3. Incluir manual local, Ajuda e informação Sobre com versão/canal de apoio.
4. Documentar e ensaiar cópia de segurança e restauro.
5. Validar numa estação CRL: PDF textual, digitalização, tabela complexa, `L:`
   real, permissões, interrupção/retoma e entrega/importação no MAXQDA.
6. Publicar requisitos medidos, limitações conhecidas e ficha de aceitação
   associada ao hash do EXE final.

Para um piloto acompanhado, a paragem controlada, entrega sem bloqueio e
melhorias de escala devem ser priorizadas conforme os lotes e ecrãs usados.
Se impedirem terminar tarefas na estação de destino, tornam-se condições de
aceitação dessa distribuição. O modo de trabalho inicial deve ter um escritor
por pasta, mesmo após introduzir bloqueios, até validar partilhas reais.

Podem esperar: atualização automática, editor visual de tabelas, edição de
vocabulários pela GUI, descoberta automática de índices e colaboração simultânea
com resolução de conflitos. Não são necessários para provar o percurso principal.

## Validação desta revisão

- Executado `.venv/bin/python -m pytest -q`: 624 aprovados, 31 omitidos e
  uma falha ao criar um socket Unix local, bloqueado pela sandbox.
- Repetido apenas esse teste fora da sandbox: aprovado (1 teste).
- Resultado agregado: os 625 testes não omitidos passaram, considerando a
  repetição isolada; não se apresenta isto como uma execução integral sem falhas.
- As omissões incluem ensaios condicionais de Windows/GUI e corpus externo.
- Os achados de interface e instalador resultam de leitura do código; não foi
  executado o instalador, nem simulado visualmente o editor nesta revisão.
- Só foi acrescentada documentação de revisão; não foram alteradas funcionalidades.

Avaliação qualitativa: correção/integridade tem boas salvaguardas, com a lacuna
de concorrência no catálogo; segurança tem bom isolamento offline, com aceitação
institucional da distribuição pendente; desempenho tem mitigação para falhas
nativas, mas requer medição na estação; manutenção tem testes e versões fixadas,
mas precisa de fechar documentação, compatibilidade e ciclo de atualização.
