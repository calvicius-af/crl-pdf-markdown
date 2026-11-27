# Comparar com a versão completa anterior

Cada revisão global publicada no ano é comparada, cláusula a cláusula, com a
versão completa anterior da mesma convenção. O resultado é um Excel por
convenção, em `3_analise/comparacoes`.

Enquanto não houver índices BTE dos anos anteriores, a versão anterior é
descarregada à mão. A aplicação prepara as pastas e diz o que falta.

## 1. Preparar as pastas

Depois da recolha e da nomeação (`collect` e `name --aplicar`):

```powershell
.venv\Scripts\python.exe -m crl_markdown prepare-comparisons --workspace C:\Dados\RNC_Dados_2026
.venv\Scripts\python.exe -m crl_markdown prepare-comparisons --workspace C:\Dados\RNC_Dados_2026 --aplicar
```

O primeiro comando só simula. Com `--aplicar`:

1. para cada convenção cujo título indica «Revisão global», é criada a pasta
   `3_analise/comparacoes/<nome do ficheiro original>/`, por exemplo
   `2026_BTE_01_PRI_016_ACT_17203_BRISA-SETACCOP+12/`;
2. o PDF actual é copiado para essa pasta, com o mesmo nome, verificado pelo
   SHA-256;
3. é escrito `3_analise/comparacoes/pendentes.csv`, com uma linha por convenção.

Nada é apagado nem substituído. As pastas criadas antes pela equipa, com outros
nomes, não são tocadas.

## 2. Descarregar a versão anterior

A coluna `versao_anterior_indice` do `pendentes.csv` diz que documento a
revisão altera, segundo o índice do ano (coluna `DocAlteradosPorEste`). Por
exemplo, `ACT 484/2024, publicado a 08/11/2024`.

Quando `aviso_indice` diz «Alteração parcial», esse documento só tem as
cláusulas alteradas. Procure, para trás, o último texto completo: revisão
global, alteração com texto consolidado ou convenção inicial.

Ponha o PDF da versão anterior na pasta da convenção, com qualquer nome que não
seja o do PDF actual. Se puser mais de um, a comparação usa o que tiver o ano
mais recente no nome, e avisa.

A coluna `observacoes` é da equipa e é conservada quando o ficheiro é refeito.

## 3. Comparar

```powershell
.venv\Scripts\python.exe -m crl_markdown compare --workspace C:\Dados\RNC_Dados_2026
.venv\Scripts\python.exe -m crl_markdown compare --workspace C:\Dados\RNC_Dados_2026 --pasta 2026_BTE_01_PRI_016_ACT_17203_BRISA-SETACCOP+12 --anterior C:\caminho\outra_versao.pdf
```

Sem `--pasta`, são comparadas todas as pastas que têm a versão anterior. Uma
comparação já feita só é refeita com `--substituir`. No fim, os estados do
`pendentes.csv` são actualizados.

### Estados no `pendentes.csv`

| Estado                     | Significado                                            |
| -------------------------- | ------------------------------------------------------ |
| `a_criar`                  | Na simulação: a pasta será criada                      |
| `por_nomear`               | A revisão global ainda não tem nome; corra a nomeação  |
| `sem_pdf_actual`           | O PDF actual falta ou tem hash diferente do registo    |
| `sem_anterior`             | Falta a versão anterior na pasta                       |
| `anterior_igual_ao_actual` | O PDF posto como anterior é o próprio documento actual |
| `varias_anteriores`        | Há mais de um PDF anterior; confirmar o escolhido      |
| `pronta`                   | Pronta para comparar                                   |
| `comparada`                | Comparação feita                                       |

## 4. Ler o Excel

O ficheiro `<pasta>_comparacao.xlsx` tem três folhas.

**Comparação.** Uma linha por cláusula, artigo ou anexo, ordenada por
importância: novas, alteradas, removidas, alterações formais, iguais.

| Classificação      | Significado                                                                                    |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| `nova`             | Sem correspondente na versão anterior                                                          |
| `alteracao`        | O conteúdo mudou                                                                               |
| `removida`         | Sem correspondente na versão actual                                                            |
| `alteracao_formal` | Só muda o espaçamento, a pontuação, a translineação ou a grafia anterior ao Acordo Ortográfico |
| `=`                | Texto igual (sem contar acentos, maiúsculas e espaços repetidos)                               |

A coluna **Diferenças** mostra o que mudou, palavra a palavra, com algum
contexto: `[-texto retirado-]` e `{+texto acrescentado+}`. **Números
alterados** assinala as cláusulas em que algum valor mudou. **Renumerada**
assinala as cláusulas que mudaram de número e foram emparelhadas pelo conteúdo.

**Resumo.** Contagem por classificação.

**Proveniência.** Ficheiros comparados, hashes, extracção usada, versão da
aplicação, limiares e avisos.

### Extracção usada

Se o PDF já foi convertido para Markdown na mesma pasta RNC
(`2_processamento/texto`), a comparação usa essa extracção Docling, encontrada
pelo hash do PDF. Caso contrário, lê o PDF com pdfplumber, como o AppCCT, e
avisa na folha Proveniência: as diferenças usadas na análise devem então ser
confirmadas no PDF.

## Como o emparelhamento funciona

Porta o comparador do AppCCT (`cct/diacronia.py`):

1. primeiro pelo número («12.ª» e «décima segunda» são a mesma cláusula),
   aceite se o conteúdo for parecido (semelhança de pelo menos 0,5) ou o título
   coincidir (0,8);
2. depois, as que sobram, pelo conteúdo (0,75), o que apanha renumerações.

Diferença face ao AppCCT: «igual» exige texto igual. O limiar de 0,995 do AppCCT
dava como iguais cláusulas longas em que só mudava um valor (por exemplo,
4,29 € para 4,42 € no BTE 1/2026, cláusula 27.ª da BRISA).
