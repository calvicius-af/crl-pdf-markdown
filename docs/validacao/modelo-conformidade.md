# Relatório de conformidade documental — modelo por lote

Estado inicial: por preencher. Este modelo não aprova nenhum documento.

## Identificação e âmbito

- Lote, ano, objetivo da análise, responsáveis e datas: [preencher].
- Índices, folhas/linhas e critérios de inclusão/exclusão: [preencher].
- PDFs, URLs, unidades documentais/recortes e hashes: [manifesto correspondente].

## Método efetivamente aplicado

Descrever recolha, nomeação, motor Docling/modelos/parâmetros, OCR, normalização,
perfil Markdown, ordem/tabelas e organização de resultados. Identificar versão
da app, código, sistema, Python e dependências. Declarar reutilização de cache
e referências alternativas não independentes. Não descrever passos não executados.

## Verificações e resultados

| Controlo | Método/referência | Critério | Resultado real | Evidência |
| --- | --- | --- | --- | --- |
| Reconciliação do índice | [preencher] | Todas as entradas com desfecho | Por verificar | [ficheiro] |
| Integridade dos PDFs e cópias | SHA-256 | Hashes conferidos | Por verificar | [ficheiro] |
| Conteúdo e ordem | Métricas + inspeção | Limiares identificados e perdas críticas resolvidas | Por verificar | [ficheiro] |
| Caracteres/símbolos/valores | Comparação específica | Sem alterações críticas conhecidas | Por verificar | [ficheiro] |
| Estrutura e marcadores | Rótulos/hierarquia contra PDF | Correspondência verificada | Por verificar | [ficheiro] |
| Tabelas | Células, categorias, valores e notas | Relações corretas | Por verificar | [ficheiro] |
| Revisão humana | Plano e amostra documentados | Extensão explícita | Por verificar | [ficheiro] |
| Importação MaxQDA | Versão/opções e observação | Legibilidade, pesquisa e codificação | Por verificar | [ficheiro] |

## Revisão e alterações

População, critérios de risco, seleção/tamanho/semente da amostra, documentos e
páginas conferidos, responsáveis, defeitos, alterações antes/depois e decisões.
Cada aprovação identifica o hash da versão aprovada, não apenas o nome do ficheiro.

## Balanço e limitações

Totais selecionados, convertidos, sem alertas, a rever, bloqueados, aprovados,
rejeitados e pendentes: [preencher e reconciliar]. Estas categorias pertencem a
etapas distintas; indicar denominadores e não somá-las como se fossem disjuntas.

Listar controlos indisponíveis, divergências, OCR, imagens, tabelas complexas,
partes não revistas e limitações de importação. Ausência de alerta não demonstra
igualdade carácter a carácter. Não alegar garantia estatística sem plano aprovado.

## Conclusão e decisão

> O corpus foi preparado a partir de [fontes], conservando os PDF de referência.
> Usou-se [motor/versão/modelos], com [regras/OCR]. Todos os documentos passaram
> por [controlos efetivos]. A revisão visual incidiu em [extensão/seleção].
> Foram identificados [defeitos], dos quais [resolvidos/pendentes]. Foram aprovados
> [N] documentos, identificados por [hashes], para [utilização]. A importação foi
> verificada em [MaxQDA/versão], por [procedimento], com [resultado]. A evidência
> sustenta [conclusão delimitada], com [limitações].

Responsável, data e decisão: [preencher]. Anexar manifesto, resultados por documento,
inventário de tabelas e registo de alterações. Este relatório é metodológico,
não uma certificação jurídica do conteúdo.
