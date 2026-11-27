"""Acrescenta à lista_siglas_global as siglas novas e as decisões da equipa, e regera o siglas.csv.

Entradas (as duas escritas pela recolha, ao lado do registo):

1. `--novas siglas_novas.csv`: entidades fora da lista que receberam sigla por
   regra. Entram todas, sem revisão (decisão de 2026-11-27), com um
   `id_entidade` NOM-NNNN. Uma entidade que já esteja na lista não se repete.
2. `--decisoes siglas_pendentes.csv`: siglas que bloqueiam documentos. Só as
   linhas com `aprovar` na coluna `decisao` contam. A entidade é a do
   `id_entidade` da linha ou, sem ele, a de nome com a mesma grafia exata
   (Mosteiro e Mosteirô são diferentes), ou a que tem esse nome como rótulo
   CRL. A sigla aprovada passa a ser a dela, sem pendentes em `revisao`; outras
   entidades com a mesma grafia e outra sigla ficam `Desativada`. Um nome fora
   da lista cuja sigla já pertence a uma só entidade entra como rótulo dela;
   senão, entra como entidade nova.

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


def _rotulos(linha: dict) -> list[str]:
    return [r.strip() for r in (linha.get("rotulos_crl") or "").split("|") if r.strip()]


def _ativa(linha: dict) -> bool:
    return (linha.get("estado") or "").strip().casefold() != "desativada"


def _sigla(valor: str) -> str:
    return nomeacao.normalizar_sigla(valor).casefold()


def aplicar(lista: list[dict], novas: list[dict], decisoes: list[dict], hoje: str) -> dict:
    """Altera `lista` no lugar e devolve o relatório do que mudou.

    A entidade identifica-se pelo `id_entidade` da decisão ou, sem ele, pela
    grafia exata do nome (`chave_grafia`), nunca pela chave sem acentos:
    Mosteiro e Mosteirô são entidades diferentes. Um nome que é rótulo CRL de
    uma entidade (`rotulos_crl`) aplica a decisão a essa entidade."""
    rel = {"acrescentadas": [], "ja_na_lista": [], "aprovadas": [], "desativadas": [],
           "rotulos": [], "ignoradas": 0}
    por_id = {linha.get("id_entidade", ""): linha for linha in lista if linha.get("id_entidade")}
    por_grafia: dict[str, list[dict]] = {}
    por_rotulo: dict[str, list[dict]] = {}
    for linha in lista:
        por_grafia.setdefault(nomeacao.chave_grafia(linha["nome"]), []).append(linha)
        for rotulo in _rotulos(linha):
            por_rotulo.setdefault(nomeacao.chave_grafia(rotulo), []).append(linha)
    ident = _proximo_id(lista)

    def acrescentar(nome, sigla, categoria):
        nonlocal ident
        linha = _nova(nome, sigla, ident, hoje, categoria)
        ident += 1
        lista.append(linha)
        por_id[linha["id_entidade"]] = linha
        por_grafia.setdefault(nomeacao.chave_grafia(nome), []).append(linha)
        return linha

    for nova in novas:
        nome, sigla = nova.get("nome", "").strip(), nova.get("sigla", "").strip()
        if not nome or not sigla:
            rel["ignoradas"] += 1
            continue
        grafia = nomeacao.chave_grafia(nome)
        if grafia in por_grafia or grafia in por_rotulo:
            rel["ja_na_lista"].append(nome)
            continue
        linha = acrescentar(nome, sigla, nova.get("categoria") or "Entidade nova")
        rel["acrescentadas"].append((linha["id_entidade"], sigla, nome))

    for decisao in decisoes:
        if (decisao.get("decisao") or "").strip().casefold() not in APROVAR:
            rel["ignoradas"] += 1
            continue
        nome, sigla = decisao.get("nome", "").strip(), decisao.get("sigla", "").strip()
        if not nome or not sigla:
            rel["ignoradas"] += 1
            continue
        grafia = nomeacao.chave_grafia(nome)
        ids = [i for i in (decisao.get("id_entidade") or "").split() if i in por_id]
        pelo_rotulo = False
        if ids:
            candidatos = [por_id[i] for i in ids]
        else:
            candidatos = [linha for linha in por_grafia.get(grafia, []) if _ativa(linha)]
            if not candidatos:
                candidatos = [linha for linha in por_rotulo.get(grafia, []) if _ativa(linha)]
                pelo_rotulo = bool(candidatos)
        if not candidatos:
            # Fora da lista: um nome alternativo de uma entidade que já tem esta
            # sigla entra como rótulo dela; senão, é uma entidade nova.
            donos = {id(linha): linha for linha in lista if _ativa(linha) and _sigla(linha["sigla"]) == _sigla(sigla)}
            if len(donos) == 1:
                dono = next(iter(donos.values()))
                dono["rotulos_crl"] = " | ".join([*_rotulos(dono), nome])
                dono["data_atualizacao"] = hoje
                por_rotulo.setdefault(grafia, []).append(dono)
                rel["rotulos"].append((dono["id_entidade"], sigla, nome))
            else:
                linha = acrescentar(nome, sigla, "Entidade nova (aprovada pela equipa)")
                rel["aprovadas"].append((linha["id_entidade"], sigla, nome))
            continue
        escolhida = next((linha for linha in candidatos if _sigla(linha["sigla"]) == _sigla(sigla)), candidatos[0])
        escolhida["sigla"], escolhida["revisao"], escolhida["data_atualizacao"] = sigla, "", hoje
        rel["aprovadas"].append((escolhida["id_entidade"], sigla, nome))
        for outra in candidatos:
            if outra is escolhida or _sigla(outra["sigla"]) == _sigla(sigla):
                continue
            if pelo_rotulo:
                # O rótulo deixa de apontar para as outras entidades.
                outra["rotulos_crl"] = " | ".join(
                    r for r in _rotulos(outra) if nomeacao.chave_grafia(r) != grafia)
                outra["data_atualizacao"] = hoje
                continue
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
    print(f"Decisões aprovadas: {len(rel['aprovadas'])}; nomes acrescentados como rótulo: {len(rel['rotulos'])}; "
          f"linhas desativadas: {len(rel['desativadas'])}; "
          f"linhas ignoradas (sem aprovar ou incompletas): {rel['ignoradas']}.")
    for ident, sigla, nome in rel["acrescentadas"] + rel["aprovadas"] + rel["rotulos"]:
        print(f"  {ident}: {sigla} = {nome}")
    if args.siglas:
        print(regerar(args.lista, args.siglas))
    else:
        print("Nenhum --siglas indicado: o siglas.csv não foi regerado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
