# SPEC-0001 — Fechar o percurso documental PDF → Markdown

- Estado: em desenvolvimento; requisitos propostos e implementação parcial.
- Data: 13/10/2026.
- Repositório responsável: `crl-pdf-markdown`.
- Origem: nota ditada e seis orientações adicionais de António Fula.
- Contexto: fork do `crl-app-cct`, que fornece regras e vocabulários.

## Objetivo e fronteira do produto

Preparar um corpus de documentos publicados no BTE, a partir dos índices recebidos,
com nomes estáveis, texto Markdown legível e estrutura jurídica preservada,
evidência de fidelidade ao PDF e método documentado para análise qualitativa no MaxQDA.
O PDF publicado é a fonte de referência; o Markdown é uma representação derivada.

```text
Índice → recolha → nomeação/cópia → Docling → normalização → Markdown
       → controlos → revisão humana → corpus aprovado → MaxQDA
```

Preparação, revisão, importação e conformidade são etapas distintas. Não executar
pré-codificação, diacronia, LLM ou QDPX como requisito da preparação documental.
Copilot/SharePoint é um destino adicional futuro, sujeito às verificações próprias.

## Orientações incorporadas

| Origem       | Orientação                                                         | Concretização                                                                         |
| ------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| Nota inicial | Retirar PDF a partir do ficheiro da DGCP                           | Recolha reconciliada por entrada, URL, ID e hash                                      |
| Nota inicial | Renomear e guardar noutra pasta                                    | Árvore RNC, nomes ADR-0022 (decisão de 13/10), cópias verificadas e catálogo          |
| Nota inicial | Extrair e arrumar em Markdown                                      | Docling, regras jurídicas, cache e normalização conservadora                          |
| Nota inicial | Preservar capítulos, secções, cláusulas/artigos, números e alíneas | Inventário estrutural, marcadores originais e testes de regressão                     |
| Nota inicial | Enter antes de cláusulas; boa legibilidade                         | Pelo menos uma linha em branco antes de cada cláusula/artigo                          |
| Nota inicial | Máxima fidelidade e tabelas legíveis                               | Conteúdo, caracteres, ordem e células, com conferência dos casos de risco             |
| Nota inicial | Relatório de conformidade e ficha metodológica                     | Método por lote, controlos, revisões, limites e decisão                               |
| Orientação 1 | Estrutura segundo o README fornecido                               | init e organização por fase; adaptar saídas QDPX a Markdown                           |
| Orientação 2 | Adotar cedo a nomeação final                                       | name em simulação/aplicação; não gerar mais nomes provisórios canónicos               |
| Orientação 3 | siglas.csv consolidado                                             | Listas oficiais/equipa e complemento AppCCT, proveniência e ambiguidades              |
| Orientação 4 | Instalação offline suave e recuperável sem o autor                 | Pacote completo, lançador, integridade, isolamento local e instruções de reparação    |
| Orientação 5 | Docling predominante apesar da lentidão                            | Docling ACCURATE; cache auditada para reaplicar regras; sem troca silenciosa de motor |
| Orientação 6 | Falhas autocontidas e acessíveis                                   | Explicação + ação + documento/etapa + detalhe técnico arquivado                       |

## Estado real do fork

O fork já tinha Markdown estruturado, regras herdadas, JSON Docling persistente,
cache com hashes, auditoria do Markdown final, verificação de montantes e relatórios
por corrida. A especificação anterior, escrita no AppCCT, subestimava estas capacidades.
Esta versão substitui-a e concentra-se nas lacunas efetivas.

Nesta integração foram acrescentados árvore RNC, comandos init/name/doctor,
catálogo de nomeação, siglas consolidadas, relatórios de recolha, recuperação de
falhas de operação e ferramentas de pacote/instalação offline. Não se declara
concluída a validação de estação, a importação MaxQDA ou a revisão do corpus.

## Requisitos obrigatórios e aceitação

### RF-01 — Recolha e unidade documental

Cada entrada selecionada do índice tem desfecho: adquirida, existente, falhada,
excluída ou pendente, com motivo. Guardar índice/folha/linha, URL, ID, tamanho e
SHA-256. Uma resposta HTML não pode ser aceite como PDF. A rede requer autorização.
Preservar duplicados de catálogo que representem relações distintas; não apagar
silenciosamente entradas porque partilham conteúdo.

Um boletim completo não é uma convenção individual. Quando se recorta, guardar
referência ao boletim, páginas verificadas e hash próprio do recorte.

Aceitação: contagens reconciliadas com o índice; repetição sem duplicação ou
substituição de PDF diferente; erros por documento não impedem os restantes.
Recorte histórico automático continua por integrar no fork.

### RF-02 — Nomes estáveis e organização

Seguir [organização RNC](../docs/organizacao-rnc.md), baseada no documento fornecido.
Conservar nome de origem e atribuir nome canónico à entrada; extensões derivadas
herdam o mesmo nome base. Fonte canónica não é corrigida nem renomeada no meio
da análise. Siglas incertas, campos em falta e conflitos ficam explicitamente pendentes.

Aceitação: hash antes/depois igual; catálogo permite regressar ao PDF e ao índice;
nome já atribuído não muda automaticamente; revisões humanas não são sobrescritas.
As convenções podem ser nomeadas agora; PE/AA aguardam confirmação dos metadados
de base e representação final. A escrita inicial não usa adivinhação para resolver isso.

### RF-03 — Vocabulário de siglas

Conservar denominação, variantes históricas, código, lado, sigla, origem, estado
e fonte. Preservar desambiguações já fixadas quando sustentadas pelo registo.
As listas de empregadores/sindicatos são independentes, não pares por linha.
Correspondências aproximadas não confirmam identidade. Propostas e colisões
não podem entrar automaticamente nos nomes. Uma decisão humana tem responsável,
data e fonte; nova consolidação não pode apagar essas decisões.

Aceitação: CSV legível por Excel/aplicação, proveniência verificável e construção
repetível; teste de unicidade entre linhagens nas linhas documentadas. Regenerar
para ficheiro de proposta e comparar antes de alterar o CSV ativo.

### RF-04 — Docling e persistência

Docling é o motor principal, com reconstrução de tabelas ACCURATE e serviços
remotos/plugins externos desligados. Guardar exportação nativa, itens/geometria
JSON, Markdown final, relatórios, versões/opções e hashes. A cache auditada serve
para reaplicar regras, sem se passar por uma nova extração.

Aceitação: cada documento permite distinguir extração, normalização e renderização;
cache só reutilizada se PDF e extração conferirem; motor/versão registados.
PDFium e pdfplumber são auditores e referências auxiliares, não uma substituição
silenciosa do motor por razões de desempenho. Uma referência alternativa não
independente tem de ser assinalada.

### RF-05 — Fidelidade e estrutura jurídica

Arrumar significa reparar extração/apresentação, não reescrever o original.
Preservar palavras, pontuação, acentos, símbolos, valores, datas, remissões,
preâmbulos, assinaturas, notas de depósito, anexos e regulamentos. Manter títulos,
ordinais romanos/por extenso, rótulos sem número, `[Revogado.]` e irregularidades
autênticas. Não inferir números ou completar texto em falta.

Hierarquia efetiva: capítulo → secção → cláusula/artigo → número → alínea,
incluindo hierarquias locais dos anexos. Uma linha em branco precede cada
cláusula/artigo, exceto no início. Números/alíneas são parágrafos distinguíveis;
marcadores `1-`, `1.`, `a)` etc. conservam o designador original, sem bullets nem
renumeração pelo Markdown. UTF-8 sem BOM e quebras LF.

Aceitação: conteúdo e rótulos coincidem com a referência conferida; normalização
estável e regras justificadas; duvidoso fica para revisão. A introdução de
espaços/títulos não pode invalidar offsets: os nós atuais do fork referem-se ao
texto estruturado, não ao Markdown com marcação.

O relatório conserva normalizações de itens por página/nó e diferença entre
Markdown bruto/final, além dos nós e do texto de referência dos offsets.
Por completar: ciclo de correção manual com nova auditoria e histórico de versões;
editar diretamente um resultado invalida a aprovação e a retoma.

### RF-06 — Tabelas

Preservar linhas, colunas, cabeçalhos, valores, categorias, unidades, períodos e
notas; conferir rotação, continuação multipágina, grelhas sem traços, células
fundidas/aninhadas e tabelas em imagem. Contagem de palavras não demonstra relações.
Onde Markdown não conseguir representar a estrutura, conservar grelha estruturada
e apresentação explícita validada; uma imagem auxilia a conferência, mas não
substitui texto pesquisável/codificável exigido.

Aceitação: células e relações relevantes coincidem com o PDF. Sobreposições,
montantes alterados e conteúdo em imagem sem transcrição ficam bloqueados até
resolução. OCR local só é aprovado depois de conferir sinais, dígitos e decimais.

### RF-07 — Controlo de qualidade e revisão

Medir conteúdo, caracteres críticos, estrutura, ordem, legibilidade e tabelas.
Os limiares herdados (cobertura ≥99,5%, excesso ≤0,5%, ordem ≥97%) são triagem,
não certificado de igualdade. Tokens não representam toda a pontuação/símbolos.
Referência indisponível ou falível tem de ser registada.

Manter os estados automáticos existentes `passed`, `review`, `blocked`. Acrescentar
decisão humana distinta — pendente/aprovado/rejeitado — com responsável, data,
hash e âmbito verificado. Não confundir com faixas temáticas do AppCCT.

Aceitação: zero defeitos críticos conhecidos por resolver no corpus aprovado;
documentos pendentes disponíveis para diagnóstico, mas separados do corpus
aprovado. Os comandos review/deliver e os botões da interface implementam decisões
por hash e entrega de documentos com revisão integral. Uma amostra não aprova
automaticamente o restante lote.

Plano inicial de revisão: todos os casos com OCR, imagens, erros, auditoria
indisponível ou divergência; no primeiro lote de aceitação, todas as tabelas,
rótulos e marcadores e leitura integral de cada classe difícil; amostra aleatória
reprodutível dos restantes. Registar população, tamanho, seleção e semente.
Se um defeito crítico surgir, suspender a classe afetada, corrigir e alargar a revisão.
Não alegar uma garantia estatística enquanto amostra/tolerância não forem definidas.

### RF-08 — Instalação offline e recuperação

Pacote completo por sistema/arquitetura/Python: aplicação, wheels transitivos,
versões fixadas, modelos, vocabulários, guias e manifesto. Instalar localmente
por utilizador, mesmo a partir de uma partilha; sem compilação, privilégios admin
ou pedidos de rede. Verificar integridade, conservar instalação anterior e usar
o Python correto no lançador. OCR deve ter todos os modelos locais se for utilizado.

Aceitação: pessoa com baixas competências digitais instala e abre seguindo o
guia; erro dá instrução específica e relatório para apoio; teste real Windows
3.13, unidade mapeada/UNC, pacote só de leitura, caminhos com espaços e rede desligada.
Ferramentas foram preparadas; estes gates de estação continuam pendentes.

### RF-09 — Falhas documentadas e acessíveis

Em instalação, recolha, nomeação, extração, cache, controlo e exportação: registar
operação, documento/linha/página quando conhecidos, data, erro, versões/opções,
estado dos resultados e recuperação. Conservar traceback para apoio sem exigir
que a analista o interprete. Nenhum resultado antigo deve parecer sucesso atual.

Formato de mensagem: «O que aconteceu», «O que fazer agora», «Se continuar» e
localização do relatório. Linguagem concreta; próximos passos executáveis sem o autor.
Mensagens desconhecidas não recebem uma causa inventada: a proposta de recuperação
é uma tentativa e a evidência técnica continua disponível.

Aceitação: provocar falhas de ficheiro, permissão, modelos, dependência, timeout,
PDF inválido e escrita do relatório; verificar instruções e arquivo. Os caminhos
já cobertos foram implementados, mas falhas anteriores ao Python e impossibilidade
de escrita em todas as localizações têm limites explícitos nos guias.

### RF-10 — MaxQDA e conformidade metodológica

Demonstrar importação direta de Markdown na versão usada pela equipa, incluindo
títulos, separação de cláusulas, marcadores, tabelas, pesquisa e seleção/codificação.
Se MD não cumprir, documentar uma representação derivada como decisão própria;
não reintroduzir automaticamente QDPX. O ensaio QDPX de 02/10 não comprova a
importação direta e continua não aprovado.

Relatório por lote: fontes/seleção, passos, ambiente/modelos, hashes, regras,
controlos/fórmulas/limiares, revisão/amostra, alterações, totais reconciliados,
importação testada, limitações e decisão. Usar o [modelo](../docs/validacao/modelo-conformidade.md).
O relatório documenta conformidade metodológica, não certificação jurídica.

Aceitação: tudo é sustentado por artefactos/decisões reais; verificações em falta
permanecem em falta; conclusão declara a extensão da fidelidade demonstrada.
A entrega gera conformidade.json/Markdown com hashes, resultados e revisões reais.
Fontes/seleção do índice e ensaio MAXQDA do lote precisam ainda de integrar o
relatório completo; não são inferidos de uma aprovação textual.

## Ordem para concluir

1. Validar nomes/metadados nos índices reais e fechar PE/AA, variantes de siglas
   e âmbito pendentes. Migrar só com correspondências/hashes e proteção de trabalho humano.
2. Prova pequena de importação direta no MaxQDA para confirmar apresentação final.
3. Resolver os bloqueios Docling do corpus, com regras gerais e testes por caso.
4. Implementar alterações rastreáveis e decisão humana/promoção vinculada a hashes.
5. Validar pacote offline na estação e ensaiar recuperação por alguém que não seja o autor.
6. Gerar relatório metodológico a partir dos dados efetivos e realizar o ensaio integral.

## Questões a fechar

- MAXQDA 27.0.0: importação direta e codificação simples demonstradas; falta
  concluir o perfil e a conferência de estruturas jurídicas/tabelas complexas.
- Campos/identidade da convenção de base para PE/AA e representação de portarias
  com referências como `457/2025/1`.
- Quem confirma siglas/âmbito e quem aprova cada lote; amostra e tolerância de revisão.
- Âmbito documental efetivo, incluindo APU, anexos digitalizados e boletins históricos.
- Confirmação da proveniência/organismo do índice: a nota refere DGCP, os ficheiros
  e código histórico também usam DGERT. Conservar a evidência sem harmonização inventada.

## Definição de conclusão

- [ ] Índice e desfechos reconciliados; originais e recortes rastreáveis.
- [ ] Nomes finais confirmados, incluindo famílias previstas para o corpus.
- [ ] Siglas e âmbito pendentes tratados, sem junções aproximadas.
- [ ] Markdown fiel, estruturado e legível, com tabelas conferidas.
- [ ] Corpus de regressão aprovado e nenhum defeito crítico conhecido no corpus entregue.
- [ ] Alterações e revisão humana documentadas e preservadas entre execuções.
- [ ] Instalação e recuperação offline demonstradas na estação, sem intervenção do autor.
- [ ] Falhas localizadas e explicadas com próximos passos claros.
- [ ] Importação e codificação demonstradas no MaxQDA da equipa.
- [ ] Relatório metodológico por lote, com evidência, limitações e decisão de utilização.
