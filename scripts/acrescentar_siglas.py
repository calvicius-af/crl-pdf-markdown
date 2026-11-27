"""Acrescenta à lista_siglas_global as siglas novas e as decisões da equipa, e regera o siglas.csv.

Entradas (as duas escritas pela recolha, ao lado do registo):

1. `--novas siglas_novas.csv`: entidades fora da lista que receberam sigla por
   regra. Entram todas, sem revisão (decisão de 2026-11-27), com um
   `id_entidade` NOM-NNNN. Uma entidade que já esteja na lista não se repete.
2. `--decisoes siglas_pendentes.csv`: siglas que bloqueiam documentos. Só as
   linhas com `aprovar` na coluna `decisao` contam. A sigla da linha passa a
   ser a da entidade na lista, sem pendentes em `revisao`; outras linhas com o
   mesmo nome e outra sigla ficam `Desativada`. Se a entidade não estiver na
   lista, entra como nova.

A lista é reescrita no mesmo sítio, e cada `--siglas` indicado (com o manifesto
ao lado) é regerado a partir dela.
"""

import argparse
import csv
import importlib.util
import io
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from crl_markdown import nomeacao  # noqa: E402

APROVAR = {"aprovar", "aprovado", "aprovada", "sim", "s"}


def _gerador():
    spec = importlib.util.spec_from_file_location("gerar_siglas", RAIZ / "scripts/gerar_siglas_da_lista_global.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _ler(caminho: Path) -> tuple[list[str], list[dict], str]:
    bruto = Path(caminho).read_bytes().decode("utf-8-sig")
    fim = "\r\n" if "\r\n" in bruto else "\n"
    leitor = csv.DictReader(io.StringIO(bruto), delimiter=";")
    return list(leitor.fieldnames or []), list(leitor), fim


def _escrever_lista(caminho: Path, campos: list[str], linhas: list[dict], fim: str) -> None:
    texto = io.StringIO()
    escritor = csv.DictWriter(texto, fieldnames=campos, delimiter=";", lineterminator=fim,
                              extrasaction="ignore")
    escritor.writeheader()
    escritor.writerows(linhas)
    Path(caminho).write_text(texto.getvalue(), encoding="utf-8", newline="")


def _proximo_id(linhas: list[dict]) -> int:
    numeros = [int(m.group(1)) for linha in linhas
               if (m := re.fullmatch(r"NOM-(\d+)", linha.get("id_entidade", "")))]
    return max(numeros, default=0) + 1


def _nova(nome: str, sigla: str, ident: int, hoje: str, categoria: str) -> dict:
    return {"sigla": sigla, "nome": nome, "fonte": nomeacao.FONTE_REGRA, "categoria": categoria,
            "estado": "Em uso", "sigla_unica": "VERDADEIRO", "id_entidade": f"NOM-{ident:04d}",
            "data_atualizacao": hoje}


def aplicar(lista: list[dict], novas: list[dict], decisoes: list[dict], hoje: str) -> dict:
    """Altera `lista` no lugar e devolve o relatório do que mudou."""
    rel = {"acrescentadas": [], "ja_na_lista": [], "aprovadas": [], "desativadas": [], "ignoradas": 0}
    por_chave: dict[str, list[dict]] = {}
    for linha in lista:
        por_chave.setdefault(nomeacao.chave_entidade(linha["nome"]), []).append(linha)
    ident = _proximo_id(lista)

    for nova in novas:
        nome, sigla = nova.get("nome", "").strip(), nova.get("sigla", "").strip()
        chave = nomeacao.chave_entidade(nome)
        if not nome or not sigla:
            rel["ignoradas"] += 1
            continue
        if chave in por_chave:
            rel["ja_na_lista"].append(nome)
            continue
        linha = _nova(nome, sigla, ident, hoje, nova.get("categoria") or "Entidade nova")
        ident += 1
        lista.append(linha)
        por_chave[chave] = [linha]
        rel["acrescentadas"].append((linha["id_entidade"], sigla, nome))

    for decisao in decisoes:
        if (decisao.get("decisao") or "").strip().casefold() not in APROVAR:
            rel["ignoradas"] += 1
            continue
        nome, sigla = decisao.get("nome", "").strip(), decisao.get("sigla", "").strip()
        if not nome or not sigla:
            rel["ignoradas"] += 1
            continue
        chave = nomeacao.chave_entidade(nome)
        existentes = [linha for linha in por_chave.get(chave, [])
                      if (linha.get("estado") or "").strip().casefold() != "desativada"]
        if not existentes:
            linha = _nova(nome, sigla, ident, hoje, "Entidade nova (aprovada pela equipa)")
            ident += 1
            lista.append(linha)
            por_chave[chave] = [linha]
            rel["aprovadas"].append((linha["id_entidade"], sigla, nome))
            continue
        alvo = sigla_normal = nomeacao.normalizar_sigla(sigla).casefold()
        escolhida = next((linha for linha in existentes
                          if nomeacao.normalizar_sigla(linha["sigla"]).casefold() == alvo), existentes[0])
        escolhida["sigla"], escolhida["revisao"], escolhida["data_atualizacao"] = sigla, "", hoje
        rel["aprovadas"].append((escolhida["id_entidade"], sigla, nome))
        for outra in existentes:
            if outra is not escolhida and nomeacao.normalizar_sigla(outra["sigla"]).casefold() != sigla_normal:
                outra["estado"] = "Desativada"
                outra["revisao"] = f"substituída por {sigla} (decisão da equipa de {hoje})"
                outra["data_atualizacao"] = hoje
                rel["desativadas"].append((outra["id_entidade"], outra["sigla"], outra["nome"]))
    return rel


def regerar(lista: Path, destinos: list[Path]) -> str:
    gerador = _gerador()
    linhas, relatorio = gerador.converter(gerador.ler_lista(lista), lista.name)
    for destino in destinos:
        temporario = destino.with_name(destino.name + ".novo")
        temporario.unlink(missing_ok=True)
        gerador.escrever(linhas, temporario)
        temporario.replace(destino)
        manifesto = destino.with_name(destino.stem + ".manifest.json")
        gerador.escrever_manifesto(lista, destino, relatorio, manifesto)
    return gerador.texto_relatorio(relatorio)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--lista", type=Path, default=RAIZ / "vocabularios/lista_siglas_global.csv")
    p.add_argument("--novas", type=Path, help="siglas_novas.csv escrito pela recolha")
    p.add_argument("--decisoes", type=Path, help="siglas_pendentes.csv com a coluna decisao preenchida")
    p.add_argument("--siglas", type=Path, action="append", default=[],
                   help="siglas.csv a regerar (repetir para vários)")
    args = p.parse_args(argv)
    if not args.novas and not args.decisoes:
        p.error("indicar --novas, --decisoes ou ambos")
    campos, lista, fim = _ler(args.lista)
    novas = _ler(args.novas)[1] if args.novas else []
    decisoes = _ler(args.decisoes)[1] if args.decisoes else []
    rel = aplicar(lista, novas, decisoes, date.today().isoformat())
    _escrever_lista(args.lista, campos, lista, fim)
    print(f"Entidades novas acrescentadas: {len(rel['acrescentadas'])}; já na lista: {len(rel['ja_na_lista'])}.")
    print(f"Decisões aprovadas: {len(rel['aprovadas'])}; linhas desativadas: {len(rel['desativadas'])}; "
          f"linhas ignoradas (sem aprovar ou incompletas): {rel['ignoradas']}.")
    for ident, sigla, nome in rel["acrescentadas"] + rel["aprovadas"]:
        print(f"  {ident}: {sigla} = {nome}")
    if args.siglas:
        print(regerar(args.lista, args.siglas))
    else:
        print("Nenhum --siglas indicado: o siglas.csv não foi regerado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
