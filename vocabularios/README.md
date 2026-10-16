# Siglas e vocabulários consolidados

As regras sobre avisos públicos (ACEP/ACCE), deliberações e cessações estão no
[contexto de tipologias](../src/crl_markdown/vocabularios/tipologias_documentais.md),
com um [vocabulário JSON executável](../src/crl_markdown/vocabularios/tipologias_documentais.json).
Ambos são instalados em `0_gestao/vocabularios` da pasta RNC.

O ficheiro de trabalho deste fork é `../siglas.csv`, em UTF-8, separado por `;`.
O manifesto `../siglas.manifest.json` identifica fontes e hashes. A consolidação
de 13/10/2026 leu os três XLSX e a lista CSV fornecidos, complementados pelo
vocabulário AppCCT do commit `53fd77c1f18bf41d35e988ad36e49c855ed209b5`.

| Coluna             | Significado                                                                      |
| ------------------ | -------------------------------------------------------------------------------- |
| nome               | Denominação ou variante encontrada na fonte                                      |
| sigla              | Sigla canónica já documentada ou proposta legível                                |
| codigo_dgert       | Código do registo, quando a identidade foi ligada sem ambiguidade                |
| lado               | empregadores ou trabalhadores; para variantes do índice, classificação textual   |
| estado             | documentada, por_confirmar ou ambigua; confirmada pode ser atribuída pela equipa |
| origem_sigla       | Registo, desambiguação herdada, correspondência exata, índice literal ou recurso |
| fonte              | Ficheiro, folha e linha quando disponíveis                                       |
| responsavel / data | Autor e data de uma decisão humana confirmada                                    |

`documentada` é evidência nas fontes, não uma validação humana nova. A nomeação
usa a correspondência da denominação completa; uma sigla partilhada entre
linhagens não impede identificar o documento pelo ID e restantes campos.
Estados `ambigua` gerados pela consolidação por colisão de sigla não equivalem
a uma recusa humana. Duas siglas contraditórias para a mesma denominação e
decisões humanas pendentes continuam a bloquear a nomeação.

Não se associou cada empregador ao sindicato na mesma linha do CSV LISTAS:
são listas independentes de opções. Não se inventaram siglas oficiais para
empresas que usam nomes comerciais. Propostas CamelCase mantêm o seu estado
no vocabulário; podem servir como rótulos documentais automáticos, com informação
explícita de que não são siglas oficiais confirmadas. Não exigem confirmação
apenas para copiar e identificar um PDF.
Uma normalização retira acentos/pontuação para procurar nomes; não faz junções
aproximadas de entidades com palavras semelhantes. Um acrónimo num fragmento de
um nome diferente não liga esse nome ao código de outra entidade. Um acrónimo
literal no índice é conservado como evidência; se colidir com outra linhagem,
as entradas ficam ambíguas.

A versão consolidada contém 3 648 linhas: 1 740 documentadas, 154 ambíguas e
1 754 por confirmar. A aplicação lê apenas estados seguros; rejeita nomes com
siglas contraditórias e colisões entre linhagens. Variantes sem código não são
fundidas a uma identidade por semelhança textual.

Para regerar na raiz deste repositório, preferir uma saída nova e comparar:

```text
python scripts/consolidar_siglas.py --saida siglas-proposta.csv --decisoes siglas.csv
```

O comando recusa substituir um ficheiro de saída existente. `--decisoes`
conserva linhas confirmadas com responsável, data e fonte; uma confirmação
incompleta ou em colisão interrompe a construção antes de produzir a saída.
A omissão é `siglas.proposta.csv`. Não sobrescreva decisões da equipa ao regerar.
Compare a proposta e incorpore
alterações confirmadas no CSV ativo, conservando versão anterior em `9_arquivo`.
O construtor é repetível com as mesmas fontes; a nomeação não depende do AppCCT
instalado nem do seu repositório presente.

Os CSV complementares foram copiados do AppCCT: organizações, âmbito de empregadores,
atos de negociação, tipos e lista INE. A sua presença não significa que todos
os mecanismos do AppCCT tenham sido portados: o âmbito usa a lista confirmada;
INE e atos continuam disponíveis para validação e desenvolvimentos futuros.

O pacote inclui uma cópia do CSV consolidado e do manifesto em
`crl_markdown/vocabularios`. A inicialização usa estes recursos, sem depender
da raiz do repositório ou de ficheiros no diretório de execução.

Variantes com a sigla no início, no fim ou entre parênteses só recebem o código
do registo quando o nome completo normalizado, a sigla e o lado coincidem com
uma única linhagem. Uma sigla igual com um nome diferente não prova identidade.
