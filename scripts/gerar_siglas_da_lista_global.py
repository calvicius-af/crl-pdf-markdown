"""Gera o siglas.csv da nomeação a partir da lista_siglas_global.

A lista_siglas_global é a fonte única das siglas (decisão de 2026-11-26).
O siglas.csv que a nomeação lê é um derivado: não se edita à mão.

Regras da conversão:

1. Cada entidade dá uma linha com o nome, a sigla, o código DGERT (só para
   entidades da DGERT), o lado e a data de atualização.
2. Cada rótulo CRL (coluna rotulos_crl) dá uma linha extra com a mesma sigla,
   para que os nomes usados nas listas de 2025 encontrem a entidade.
3. Uma linha sem pendentes na coluna revisao fica «documentada»; uma linha com
   pendentes fica «por_confirmar» e a nomeação trata-a como pendente.
4. Duas entidades diferentes cuja sigla fica igual depois da normalização da
   nomeação (sem hífenes, sem acentos, até 20 caracteres) ficam «ambigua».
   Não se escolhe uma delas em silêncio.

O comando recusa substituir um ficheiro de saída existente.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path

from crl_markdown.nomeacao import chave_entidade, normalizar_sigla

OBRIGATORIAS = ("sigla", "nome", "fonte", "codigo_origem", "id_entidade", "lado",
                "rotulos_crl", "revisao", "data_atualizacao")
SAIDA = ("nome", "sigla", "codigo_dgert", "lado", "estado", "origem_sigla", "fonte",
         "responsavel", "data")
ORIGEM = "lista_global"
ORIGEM_ROTULO = "lista_global_rotulo"


def ler_lista(caminho: Path) -> list[dict]:
    texto = Path(caminho).read_text(encoding="utf-8-sig")
    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    em_falta = [c for c in OBRIGATORIAS if c not in (leitor.fieldnames or [])]
    if em_falta:
        raise ValueError(f"Colunas em falta na lista: {', '.join(em_falta)}")
    return list(leitor)


def converter(linhas: list[dict], nome_fonte: str = "lista_siglas_global.csv"):
    """Devolve (linhas do siglas.csv, relatório)."""
    saida = []
    for n, linha in enumerate(linhas, start=2):
        sigla = (linha["sigla"] or "").strip()
        nome = (linha["nome"] or "").strip()
        if not sigla or not nome:
            continue
        estado = "por_confirmar" if (linha["revisao"] or "").strip() else "documentada"
        dgert = (linha["fonte"] or "").startswith("Organização (DGERT)")
        base = {
            "sigla": sigla,
            "codigo_dgert": (linha["codigo_origem"] or "").strip() if dgert else "",
            "lado": (linha["lado"] or "").strip(),
            "estado": estado,
            "responsavel": "",
            "data": (linha["data_atualizacao"] or "").strip(),
            "_entidade": (linha["id_entidade"] or "").strip() or f"linha-{n}",
        }
        fonte = f"{nome_fonte}/linha {n}/{base['_entidade']}"
        saida.append({**base, "nome": nome, "origem_sigla": ORIGEM, "fonte": fonte})
        for rotulo in (linha["rotulos_crl"] or "").split("|"):
            rotulo = rotulo.strip()
            if rotulo and chave_entidade(rotulo) != chave_entidade(nome):
                saida.append({**base, "nome": rotulo, "origem_sigla": ORIGEM_ROTULO,
                              "fonte": f"{fonte}/rótulo CRL"})

    por_sigla = defaultdict(set)
    for linha in saida:
        por_sigla[normalizar_sigla(linha["sigla"]).casefold()].add(linha["_entidade"])
    colisoes = {s: sorted(e) for s, e in por_sigla.items() if len(e) > 1}
    for linha in saida:
        if normalizar_sigla(linha["sigla"]).casefold() in colisoes:
            linha["estado"] = "ambigua"

    por_nome = defaultdict(set)
    for linha in saida:
        por_nome[chave_entidade(linha["nome"])].add(normalizar_sigla(linha["sigla"]))
    nomes_contraditorios = {k: sorted(v) for k, v in por_nome.items() if len(v) > 1}

    relatorio = {
        "entidades": len({linha["_entidade"] for linha in saida}),
        "linhas": len(saida),
        "rotulos": sum(1 for linha in saida if linha["origem_sigla"] == ORIGEM_ROTULO),
        "por_estado": dict(sorted(_contar(saida, "estado").items())),
        "colisoes_de_sigla": colisoes,
        "nomes_com_siglas_diferentes": nomes_contraditorios,
    }
    return [{k: linha[k] for k in SAIDA} for linha in saida], relatorio


def _contar(linhas, campo):
    contagem = defaultdict(int)
    for linha in linhas:
        contagem[linha[campo]] += 1
    return contagem


def escrever(linhas: list[dict], destino: Path) -> None:
    destino = Path(destino)
    if destino.exists():
        raise FileExistsError(f"{destino} já existe; escolha uma saída nova e compare.")
    with destino.open("x", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=SAIDA, delimiter=";", lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(linhas)


def escrever_manifesto(lista: Path, saida: Path, relatorio: dict, destino: Path) -> None:
    """Manifesto no formato do siglas.manifest.json: fonte, contagens e hash da saída."""
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
    dados = {
        "fontes": [{"ficheiro": Path(lista).name, "sha256": sha(lista)}],
        "gerado_por": "scripts/gerar_siglas_da_lista_global.py",
        "linhas": relatorio["linhas"],
        "estados": relatorio["por_estado"],
        "sha256_saida": sha(saida),
    }
    Path(destino).write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def texto_relatorio(r: dict) -> str:
    linhas = [
        f"Entidades: {r['entidades']}; linhas escritas: {r['linhas']} "
        f"(das quais {r['rotulos']} rótulos CRL).",
        "Por estado: " + ", ".join(f"{k} {v}" for k, v in r["por_estado"].items()) + ".",
        f"Siglas que colidem depois da normalização: {len(r['colisoes_de_sigla'])}.",
    ]
    for sigla, entidades in sorted(r["colisoes_de_sigla"].items())[:20]:
        linhas.append(f"  {sigla}: {', '.join(entidades)}")
    linhas.append(f"Nomes com siglas diferentes: {len(r['nomes_com_siglas_diferentes'])}.")
    for nome, siglas in sorted(r["nomes_com_siglas_diferentes"].items())[:20]:
        linhas.append(f"  {nome}: {', '.join(siglas)}")
    return "\n".join(linhas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("lista", type=Path, help="lista_siglas_global.csv (separador ;)")
    p.add_argument("--saida", type=Path, default=Path("siglas.proposta.csv"))
    p.add_argument("--manifesto", type=Path, help="escreve também o manifesto JSON")
    args = p.parse_args(argv)
    linhas, relatorio = converter(ler_lista(args.lista), args.lista.name)
    escrever(linhas, args.saida)
    if args.manifesto:
        escrever_manifesto(args.lista, args.saida, relatorio, args.manifesto)
    print(texto_relatorio(relatorio))
    print(f"Escrito: {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
