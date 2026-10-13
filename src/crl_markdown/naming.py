"""Nomeação e cópia verificadas, com um único motor para os dois esquemas RNC."""

import copy
import csv
import errno
import os
import shutil
import tempfile
from io import StringIO
from pathlib import Path

from . import ambito, nomeacao
from .pipeline import atomic_write
from .recolha import Registo, sha256_ficheiro

key = nomeacao.chave_entidade
load_siglas = nomeacao.carregar_siglas
ASSIGNED = {"nomeado", "ja_existente", "conflito"}


def make_name(entry, table, scopes, *, scheme="adr0022"):
    """Nome sem efeitos laterais; siglas e relações incertas ficam pendentes."""
    name, warnings = nomeacao.nome_documento(entry, tabela=table,
                                           vocabulario_ambito=scopes, scheme=scheme)
    if warnings:
        raise ValueError("Sigla ou metadados por confirmar: " + "; ".join(warnings))
    employer = nomeacao.separar_outorgantes(entry.get("outorgantes", ""))[0]
    scope = ambito.classificar_com_ine(employer[0] if employer else "", entry.get("tipo", ""), scopes)[0]
    return name, scope


def _catalogs(registry, root):
    """Validar todos os catálogos antes de copiar um PDF ou alterar o registo."""
    catalogs = {}
    for year in sorted({entry["ano"] for entry in registry.entradas.values()}):
        path = Path(root) / f"0_gestao/catalogo/catalogo_irct_{year}.csv"
        rows, fields = {}, []
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle, delimiter=";")
                fields = reader.fieldnames or []
                if "chave" not in fields:
                    raise ValueError("Catálogo anterior sem chave estável; conserve-o e peça revisão ao apoio.")
                for row in reader:
                    if not row.get("chave") or row["chave"] in rows or None in row:
                        raise ValueError("Catálogo anterior com chave vazia, repetida ou linha inválida; reveja-o antes da nomeação.")
                    rows[row["chave"]] = row
        catalogs[year] = (path, fields, rows)
    return catalogs


def _csv(rows, fields=None):
    fields = list(dict.fromkeys([*(fields or []), *(field for row in rows for field in row)]))
    text = StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=fields, delimiter=";", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return text.getvalue()


def _copy_verified(source, destination, digest):
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="." + destination.name + ".", suffix=".part",
                                dir=destination.parent)
    os.close(fd)
    temporary = Path(path)
    try:
        shutil.copyfile(source, temporary)
        if sha256_ficheiro(temporary) != digest:
            raise OSError("Falha na cópia do PDF; conteúdo diferente do registo de recolha.")
        try:
            # Instalação atómica sem substituir uma criação concorrente.
            os.link(temporary, destination)
        except FileExistsError:
            if not destination.is_file() or sha256_ficheiro(destination) != digest:
                raise ValueError("Já existe outro PDF com este nome; não substituir.")
        except OSError as error:
            if error.errno not in {errno.EXDEV, errno.EOPNOTSUPP, errno.EPERM, errno.ENOSYS}:
                raise
            # Algumas partilhas não suportam hard links. A criação exclusiva
            # conserva a proteção contra substituição e apaga uma cópia incompleta.
            owned = False
            try:
                with destination.open("xb") as handle:
                    owned = True
                    with temporary.open("rb") as original:
                        shutil.copyfileobj(original, handle)
                    handle.flush()
                    os.fsync(handle.fileno())
                if sha256_ficheiro(destination) != digest:
                    raise OSError("Falha na cópia do PDF para a partilha; conteúdo diferente.")
            except FileExistsError:
                if not destination.is_file() or sha256_ficheiro(destination) != digest:
                    raise ValueError("Já existe outro PDF com este nome; não substituir.")
            except BaseException:
                if owned:
                    destination.unlink(missing_ok=True)
                raise
    finally:
        temporary.unlink(missing_ok=True)


def execute_records(registry, root, table, scopes=None, *, apply=False, scheme="adr0022",
                    families=None, workspace=True, accept_warnings=False):
    """Pré-verifica o lote; a simulação não altera identidades nem o registo."""
    if scheme not in nomeacao.ESQUEMAS:
        raise ValueError("Esquema desconhecido; use v4 ou adr0022.")
    if scopes is None:
        scopes = ambito.vocabulario_por_omissao()
    catalogs = _catalogs(registry, root) if workspace else {}
    entries = copy.deepcopy(list(registry.entradas.values()))
    nomeacao.resolver_convencoes_base(entries)
    results, plans = [], []
    for entry in entries:
        family = nomeacao._familia(entry)
        if families is not None and family not in families:
            continue
        if not workspace and (entry.get("descarga") or {}).get("estado") not in nomeacao.ESTADOS_COM_FICHEIRO:
            continue
        previous = entry.get("nomeacao") or {}
        result = {"chave": entry["chave"], "estado": "por_confirmar", "nome": "",
                  "motivo": "", "sha256": "", "ambito_origem": "", "avisos": []}
        results.append(result)
        if family in nomeacao.FAMILIAS_SO_METADADO:
            result["estado"] = "metadado"
            continue
        try:
            name, warnings = nomeacao.nome_documento(entry, tabela=table,
                                                     vocabulario_ambito=scopes, scheme=scheme)
            employers = nomeacao.separar_outorgantes(entry.get("outorgantes", ""))[0]
            scope, origin, _ = ambito.classificar_com_ine(employers[0] if employers else "",
                                                         entry.get("tipo", ""), scopes)
            result.update(nome=name, ambito_origem=origin, avisos=warnings)
            old_name = previous.get("nome") or previous.get("doc_id")
            assigned = previous.get("estado") in ASSIGNED and old_name
            if assigned and old_name != name:
                if not workspace:
                    result["estado"] = "conflito"
                raise ValueError(f"Nome já atribuído {old_name} difere da proposta; preserve o nome e reveja o conflito.")
            source = Path((entry.get("descarga") or {}).get("caminho") or "")
            digest = (entry.get("descarga") or {}).get("sha256")
            if not source.is_file() and assigned:
                source = Path(previous.get("caminho") or "")
            if not source.is_file():
                raise FileNotFoundError("PDF ainda não recolhido: " + entry.get("ficheiro", ""))
            if not digest or sha256_ficheiro(source) != digest:
                raise ValueError("Hash do PDF diferente do registo de recolha; não copiar.")
            folder = Path(root)
            if workspace:
                folder = folder / "1_fontes/irct"
            else:
                folder = folder / f"bte_{entry['ano']}"
            folder /= nomeacao.PASTA_FAMILIA[family]
            if family in nomeacao.FAMILIAS_COM_AMBITO:
                folder /= scope
            destination = folder / (name + ".pdf")
            if assigned and previous.get("caminho"):
                # Preservar também a localização atribuída; nunca migrar silenciosamente.
                destination = Path(previous["caminho"])
            if destination.exists() and (not destination.is_file() or sha256_ficheiro(destination) != digest):
                raise ValueError("Já existe outro PDF com este nome; não substituir.")
            result["sha256"] = digest
            if warnings and not accept_warnings and not assigned:
                result["motivo"] = "; ".join(warnings)
                continue
            result["estado"] = "nomeado" if assigned else "proposto"
            plans.append((entry, result, source, destination, digest, scope))
        except (ValueError, OSError) as error:
            result["motivo"] = str(error)
    destinations = {}
    for _, result, _, destination, digest, _ in plans:
        destinations.setdefault(destination, set()).add(digest)
    for entry, result, source, destination, digest, scope in plans:
        if len(destinations[destination]) > 1:
            result.update(estado="por_confirmar", motivo="Dois PDFs diferentes têm o mesmo nome no lote; reveja o índice.")
            continue
        if not apply:
            continue
        try:
            existing = destination.exists()
            if existing:
                if not destination.is_file() or sha256_ficheiro(destination) != digest:
                    raise ValueError("Já existe outro PDF com este nome; não substituir.")
            else:
                _copy_verified(source, destination, digest)
            result["estado"] = "ja_existente" if existing and not workspace else "nomeado"
            named = {**(entry.get("nomeacao") or {}), "nome": result["nome"],
                     "doc_id": result["nome"], "estado": result["estado"],
                     "caminho": str(destination), "sha256": digest, "ambito": scope,
                     "ambito_origem": result["ambito_origem"], "avisos": result["avisos"],
                     "esquema": scheme}
            original = registry.entradas[entry["chave"]]
            original["nomeacao"] = named
            for field in ("cod_irct_base", "cod_irct_base_origem", "cod_irct_base_por_resolver"):
                if field in entry:
                    original[field] = entry[field]
        except (ValueError, OSError) as error:
            result.update(estado="por_confirmar", motivo=str(error))
    if apply:
        registry.guardar()
    if workspace:
        atomic_write(Path(root) / "0_gestao/catalogo/nomeacao.csv", _csv([
            {field: value for field, value in result.items() if field != "avisos"} for result in results]))
        by_key = {result["chave"]: result for result in results}
        for year, (catalog, fields, old) in catalogs.items():
            rows = []
            for entry in registry.entradas.values():
                if entry["ano"] != year or entry["chave"] not in by_key:
                    continue
                result = by_key[entry["chave"]]
                row = {**old.pop(entry["chave"], {}), **{field: entry.get(field, "") for field in (
                    "chave", "ano", "num_bte", "id_dgert", "tipo", "familia", "titulo",
                    "cod_irct", "cod_irct_base", "outorgantes", "url", "indice", "folha", "posicao")}}
                assigned = entry.get("nomeacao") or {}
                stable = assigned.get("estado") in ASSIGNED
                row.update(nome_canonico=(assigned.get("nome") or assigned.get("doc_id")) if stable else result["nome"],
                           estado_nomeacao=assigned["estado"] if stable else result["estado"],
                           estado_proposta=result["estado"], motivo=result["motivo"],
                           sha256=assigned.get("sha256", "") if stable else result["sha256"],
                           ambito_origem=assigned.get("ambito_origem", result["ambito_origem"]) if stable else result["ambito_origem"])
                row.setdefault("observacoes_equipa", "")
                rows.append(row)
            rows.extend(old.values())
            if rows:
                atomic_write(catalog, _csv(rows, fields))
    return results


def name_records(registry, root, siglas, scopes_path=None, *, apply=False, scheme="adr0022", families=None):
    records = Registo.carregar(Path(registry))
    if not records.entradas:
        raise ValueError("Registo vazio ou inexistente. Faça primeiro a recolha a partir dos índices.")
    scopes = None
    if scopes_path is not None:
        with Path(scopes_path).open(encoding="utf-8-sig", newline="") as handle:
            scopes = {key(row["nome"]): row["ambito"] for row in csv.DictReader(handle, delimiter=";")}
    return execute_records(records, root, load_siglas(siglas), scopes, apply=apply,
                           scheme=scheme, families=families)
