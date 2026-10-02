# Validação de extração e Markdown — 1 de outubro de 2026

A versão 0.2 corrige a limitação da primeira validação, que cobria a sintaxe
Markdown e dois documentos curtos, sem medir a completude do conteúdo.

## Âmbito

- Suite: 304 testes aprovados e 6 ignorados (PDFs antigos ausentes e colisões
  de nomes num volume que não distingue maiúsculas).
- Onze ficheiros de testes recuperados de crl-app-cct (commit `53fd77c`).
- Testes novos sobre o Markdown final, conteúdo de tabelas, perda de parágrafos,
  alteração de montantes, marcadores legais, títulos e preâmbulos.
- Os 14 PDFs do corpus anterior, com hashes confirmados e uma extração Docling
  real em modo offline. Reaplicação de regras sobre esses itens guardados, com
  nova auditoria independente em cada teste.
- macOS arm64, Python 3.11.16, Docling 2.128.0.

## Corpus real

| ID BTE | Cláusulas | Artigos | Tabelas | Cobertura | Estado  |
| ------ | --------- | ------- | ------- | --------- | ------- |
| 377    | 65        | 0       | 9       | 99.752%   | review  |
| 378    | 2         | 0       | 0       | 100.000%  | review  |
| 379    | 4         | 0       | 1       | 100.000%  | review  |
| 380    | 5         | 0       | 3       | 100.000%  | review  |
| 381    | 73        | 0       | 3       | 99.746%   | review  |
| 383    | 45        | 0       | 3       | 99.693%   | review  |
| 384    | 6         | 1       | 5       | 99.565%   | blocked |
| 385    | 6         | 2       | 6       | 99.636%   | blocked |
| 386    | 4         | 0       | 3       | 100.000%  | review  |
| 382    | 82        | 0       | 7       | 99.760%   | blocked |
| 387    | 0         | 0       | 2       | 99.330%   | blocked |
| 388    | 0         | 0       | 2       | 99.329%   | blocked |
| 389    | 0         | 0       | 2       | 99.327%   | blocked |
| 390    | 0         | 0       | 2       | 99.329%   | blocked |

As contagens de cláusulas e anexos coincidem com as expectativas estruturais
do corpus anterior. As cláusulas são apresentadas com o título unido; os
preâmbulos e as assinaturas estão identificados. Na IBERCOURIER, os marcadores
das cláusulas 42.ª/43.ª foram preservados. Na ACIBARCELOS, o título longo da
68.ª foi preservado. Na APSolutions, recuperou-se a cláusula 33.ª, que o Docling
tinha confundido com uma tabela.

## Problemas ainda sinalizados

- Empresa Metropolitana: a reconstrução anterior da grelha apagava células
  com seis montantes. Os textos foram recuperados de `table_cells`; os montantes
  agora coincidem com o auditor, mas a sobreposição de posições continua a impedir
  validar a correspondência entre linhas e colunas.
- AWP e APSolutions: células sobrepostas em grelhas de categorias/funções;
  conteúdo preservado, posição a conferir.
- Quatro CARRISTUR: grelhas rodadas com sobreposições e um `1967,00` que aparece
  como `967,00` noutra posição. Os erros continuam bloqueados.
- Os restantes documentos mantêm avisos de figuras sem transcrição e, nalguns
  casos, perdas/excessos residuais de palavras. `review` não significa aprovação
  de fidelidade ao PDF.

Todos os documentos do corpus passaram nas regras markdownlint selecionadas.
Isto não remove os bloqueios de extração. O corpus mede a camada textual: não
comprova por si só o conteúdo de imagens nem a renderização no MAXQDA.

Os PDFs, extrações e diagnósticos reais ficam locais, excluídos do Git.

## Relatórios por corrida (0.2.1)

O relatório consolidado foi validado numa nova execução dos 14 PDFs do corpus,
reutilizando as extrações Docling com hashes verificados e repetindo a auditoria
independente do Markdown final. Resultado: 14 convertidos, 0 falhas, 7 documentos
a rever e 7 bloqueados; 15 erros, 205 avisos e 5 informações.

O diagnóstico reúne todas as ocorrências, os contextos e os trechos de completude,
incluindo problemas locais quando o veredicto global é `OK`. O inventário TXT e o
manifesto JSON conservam os dados de cada tentativa. As corridas anteriores ficam
arquivadas, com links relativos ajustados à localização do respetivo relatório.

A suite sem modelos nem corpus externos passou com **294 testes** e **21 testes
condicionais omitidos**. Os novos testes cobrem lotes com falhas, subpastas com
nomes repetidos, erros de inicialização, interrupções, conservação de relatórios
anteriores e inventários sem truncamento de ocorrências ou contagens de palavras.
Ruff e markdownlint passaram. A interface gráfica disponibiliza a abertura do
relatório; essa interação visual não foi testada automaticamente.

## Redução de ruído e relatório resumido (0.2.2)

Nova execução dos mesmos 14 PDFs, com cache verificada e leitura independente:
2 documentos sem alertas automáticos, 5 a rever e 7 bloqueados. Mantêm-se os
15 erros de tabelas/montantes; os avisos passaram de 205 para 48. Os 154 avisos
relativos ao pequeno logótipo do BTE foram excluídos pelo contexto textual e pela
posição e dimensão do objeto; figuras fora desse padrão continuam sinalizadas.

O resumo passou de 4 680 para 128 linhas, com ocorrências agrupadas por regra.
As evidências, contextos e proveniência ficam em `detalhes.md` e no manifesto.
Nos casos AWP e APSolutions, `ex - ceção` passou a `exceção` no próprio Markdown;
a referência independente confirma a palavra unida. A mesma regra corrigiu
outras divisões em prosa e células, sem reduzir os controlos de perdas reais.

Os testes confirmam que o mobiliário reconhecido do BTE sai da referência antes
da comparação, que citações do boletim e números no corpo são preservados, que
figuras no corpo não são tratadas como logótipos e que a reparação exige evidência
independente. A suite local passou com 299 testes e 21 omissões condicionais;
Ruff e markdownlint passaram, incluindo o resumo e os detalhes reais do lote.

## Importação experimental no MaxQDA — 2 de outubro de 2026

O QDPX construído a partir dos 14 Markdown passou nos controlos técnicos, mas o
utilizador reportou perda de formatação e variáveis sem valores atribuídos aos
casos/documentos. A experiência não foi aprovada para esses dois requisitos.
Ver o [registo do teste](docs/validacao/teste-md-qdpx-maxqda-2026-10-02.md).
