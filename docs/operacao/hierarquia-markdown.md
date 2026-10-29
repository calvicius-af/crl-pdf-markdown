# Hierarquia Markdown dos documentos

## Regra de formatação

Os níveis exprimem a relação entre as divisões publicadas. Uma cláusula dentro
de uma secção não deve ter o mesmo nível da secção. Não se inventam números de
capítulos nem se transforma a formatação em alteração do conteúdo jurídico.

| Elemento                                  | Nível normal                | Quando varia                                                                          |
| ----------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------- |
| Identificação do documento                | `#`                         | Gerada do nome do ficheiro quando falta um título principal.                          |
| Preâmbulo                                 | `##`                        | A designação gerada é identificada na proveniência.                                   |
| Capítulo ou anexo de topo                 | `##`                        | Uma parte de anexo fica subordinada ao anexo principal.                               |
| Secção dentro de capítulo                 | `###`                       | Sem capítulo, pode ser uma divisão de topo em `##`.                                   |
| Cláusula/artigo diretamente no capítulo   | `###`                       | Sem divisões superiores, fica em `##`.                                                |
| Cláusula/artigo dentro de secção          | `####`                      | Acresce um nível quando a secção está dentro de outra divisão, como anexo articulado. |
| Números e alíneas                         | Texto com marcador original | Não se transformam em títulos nem se renumeram por CommonMark.                        |
| Assinaturas / início de texto consolidado | `##`                        | Fecham a divisão anterior quando reconhecidos como blocos próprios.                   |

Exemplo com secção:

```markdown
# Identificação do documento

## CAPÍTULO VI - Prestação do trabalho

### SECÇÃO I - Princípios gerais

#### Cláusula 26.ª - Regulamentação do trabalho

1- Texto publicado.
```

Sem secção intermédia:

```markdown
## CAPÍTULO V

### Cláusula 25.ª - Garantias do trabalhador

1- Texto publicado.
```

## Articulado inicial sem capítulo numerado

No documento da Autoestrada do Algarve, o PDF começa com o título **Âmbito e
vigência**, seguido das cláusulas 1.ª a 3.ª, e só depois apresenta **CAPÍTULO II**.
Não há um rótulo CAPÍTULO I no original.

Quando existe esse título nativo, a aplicação conserva-o como divisão de topo;
as cláusulas ficam abaixo dele. Se faltarem uma divisão e um título nativo
adequado antes de capítulos posteriores, acrescenta **Articulado**, identificando
essa designação editorial em `generated_headings` e nas transformações. Os
controlos de conteúdo não a contam como palavras do PDF.

```markdown
## Âmbito e vigência

### Cláusula 3.ª - (Comissão paritária)

1- Texto publicado.

## CAPÍTULO II - Admissões e enquadramento profissional

### Cláusula 4.ª - (Condições de admissão)
```

O corpo da cláusula 3.ª termina antes do capítulo seguinte. A ausência do primeiro
rótulo não se resolve com um número presumido.

## Tabelas e limites da importação

Uma tabela conserva linhas, colunas, cabeçalhos, valores, notas e uniões. A largura
não demonstra perda de conteúdo; uma associação incorreta entre categoria, nível
e montante é um problema de fidelidade mesmo quando todos os números existem.

A reconstrução auxiliar só usa a grelha desenhada no PDF quando há correspondência
geométrica e conservação de caracteres. Conteúdo sem célula inequívoca é conservado
separadamente e gera bloqueio; não é atribuído à categoria mais próxima.

Os testes verificam a estrutura Markdown e os casos do export MAXQDA. A
renderização/importação na versão concreta do MAXQDA continua a exigir ensaio.
Não se deve substituir um documento já codificado sem o procedimento de revisão
do projeto de análise.
