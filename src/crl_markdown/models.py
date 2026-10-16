"""Modelos Docling: descarregar uma vez, verificar sempre, converter sem rede.

O Docling precisa de modelos (layout, TableFormer e, com OCR, o RapidOCR), que
vai buscar ao Hugging Face na primeira conversão. Numa estação sem acesso, ou
para garantir que nada sai da máquina, descarregam-se numa máquina com rede,
copia-se a pasta e confirma-se cada ficheiro pelo SHA-256 antes de converter:

    crl-md models download --dest PASTA    # máquina com rede; escreve o manifesto
    crl-md models verify --folder PASTA    # estação, depois de copiar a pasta
    crl-md convert ... --models PASTA --offline

Adaptado de crl-app-cct (cct/modelos_docling.py). Os modelos docling-project/*
vêm do Hugging Face, na revisão fixada pela versão do Docling instalada; os do
RapidOCR vêm da origem definida pelo próprio Docling.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

MANIFEST = "manifesto_modelos.json"

# O motor de OCR é fixado em vez de escolhido pelo Docling: a escolha automática
# depende do que está instalado e não do que está na pasta dos modelos, pelo que
# em modo offline podia ir buscar modelos à rede (medido no crl-app-cct a
# 2026-09-26). O backend torch vem sempre com o Docling; o onnxruntime não. A
# língua por omissão do RapidOCR é o chinês simplificado; os PDF são portugueses.
OCR_BACKEND = "torch"
OCR_LANGUAGE = "iso:pt"
OCR_FOLDER = "RapidOcr"


def ocr_options():
    """Opções do RapidOCR usadas na conversão e na descarga dos modelos."""
    from docling.datamodel.pipeline_options import RapidOcrOptions

    return RapidOcrOptions(backend=OCR_BACKEND, lang=[OCR_LANGUAGE])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _files(folder: Path) -> list[Path]:
    """Ficheiros dos modelos, sem manifesto, caches ou metadados do Finder."""
    return sorted(
        p
        for p in folder.rglob("*")
        if p.is_file() and p.name not in {MANIFEST, ".DS_Store"}
        and ".cache" not in p.relative_to(folder).parts
    )


def inventory(folder: Path) -> dict:
    """Manifesto da pasta: cada ficheiro com o tamanho e o SHA-256."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        docling_version = version("docling")
    except PackageNotFoundError:
        docling_version = None
    files = [
        {"path": p.relative_to(folder).as_posix(), "bytes": p.stat().st_size, "sha256": _sha256(p)}
        for p in _files(folder)
    ]
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "docling": docling_version,
        "ocr": f"{OCR_BACKEND}:{OCR_LANGUAGE}",
        "models": sorted({str(f["path"]).split("/")[0] for f in files}),
        "bytes": sum(int(f["bytes"]) for f in files),
        "files": files,
    }


def write_inventory(folder: Path) -> dict:
    manifest = inventory(folder)
    (folder / MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def verify(folder: Path) -> list[str]:
    """O que não corresponde ao manifesto: ficheiros em falta, alterados ou a mais."""
    path = folder / MANIFEST
    if not path.is_file():
        return [f"sem {MANIFEST} em {folder}: correr `crl-md models inventory` na origem"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"manifesto ilegível: {exc}; copiar novamente o pacote original"]
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list) or not manifest["files"]:
        return ["manifesto sem lista de ficheiros válida; voltar a preparar os modelos"]
    expected, problems = {}, []
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            problems.append("entrada inválida no manifesto")
            continue
        name = entry.get("path")
        if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                or name != PurePosixPath(name).as_posix()):
            problems.append(f"caminho inválido no manifesto: {name!r}")
            continue
        if name in expected:
            problems.append(f"entrada repetida: {name}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256", ""))):
            problems.append(f"SHA-256 inválido: {name}")
        if not isinstance(entry.get("bytes"), int) or entry["bytes"] < 0:
            problems.append(f"tamanho inválido: {name}")
        # Manifestos antigos podiam incluir metadados que o Finder altera ao
        # abrir a pasta. Não são modelos; tolerar também a sua remoção.
        if PurePosixPath(name).name == ".DS_Store":
            continue
        expected[name] = entry
    present = {p.relative_to(folder).as_posix(): p for p in _files(folder)}
    for name, entry in expected.items():
        if name not in present:
            problems.append(f"em falta: {name}")
        elif not present[name].resolve().is_relative_to(folder.resolve()):
            problems.append(f"ficheiro fora da pasta: {name}")
        elif (_sha256(present[name]) != entry.get("sha256")
              or present[name].stat().st_size != entry.get("bytes")):
            problems.append(f"alterado (SHA-256 ou tamanho diferente): {name}")
    problems += [f"a mais (não está no manifesto): {n}" for n in present if n not in expected]
    return problems


def has_ocr_models(folder: Path) -> bool:
    """Pré-verificação; o ensaio de conversão confirma compatibilidade e língua."""
    files = [p for p in (folder / OCR_FOLDER).rglob("*")
             if p.is_file() and p.stat().st_size and p.suffix in {".pth", ".pt", ".safetensors"}]
    return all(any(task in p.name.lower() for p in files) for task in ("det", "cls", "rec"))


def required_files_problems(folder: Path, *, ocr: bool = False) -> list[str]:
    """Perfil mínimo do pipeline fixado; integridade e execução são verificações separadas."""
    required = (
        "docling-project--docling-layout-heron/config.json",
        "docling-project--docling-layout-heron/preprocessor_config.json",
        "docling-project--docling-layout-heron/model.safetensors",
        "docling-project--docling-models/model_artifacts/tableformer/accurate/tm_config.json",
        "docling-project--docling-models/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors",
    )
    problems = [f"modelo obrigatório ausente ou vazio: {name}" for name in required
                if not (folder / name).is_file() or not (folder / name).stat().st_size]
    if ocr and not has_ocr_models(folder):
        problems.append("modelos do OCR incompletos: são necessários deteção, classificação e reconhecimento torch")
    return problems


def download(destination: Path) -> Path:
    """Descarrega os modelos que a conversão usa (precisa de rede)."""
    from docling.utils.model_downloader import download_models

    return download_models(
        output_dir=destination,
        progress=True,
        with_layout=True,
        with_tableformer=True,
        # Enriquecimentos que o pipeline não ativa: não descarregar.
        with_code_formula=False,
        with_picture_classifier=False,
        with_rapidocr=True,
        rapidocr_models=[f"{OCR_BACKEND}:{OCR_LANGUAGE}"],
    )


def add_arguments(parser):
    commands = parser.add_subparsers(dest="models_command", required=True)
    get = commands.add_parser(
        "download", help="Descarregar os modelos e escrever o manifesto (máquina com rede)"
    )
    get.add_argument("--dest", type=Path, required=True)
    for name, text in (
        ("inventory", "Escrever o manifesto com o SHA-256 de cada ficheiro"),
        ("verify", "Confirmar os ficheiros contra o manifesto"),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("--folder", type=Path, required=True)


def run_command(args) -> int:
    if args.models_command == "download":
        folder = Path(download(args.dest))
        manifest = write_inventory(folder)
        print(
            f"Modelos em {folder}: {len(manifest['files'])} ficheiros, "
            f"{manifest['bytes'] / 1e6:.0f} MB. Copiar a pasta inteira, com {MANIFEST}."
        )
        return 0
    if not args.folder.is_dir():
        raise ValueError(f"Pasta de modelos inexistente: {args.folder}")
    if args.models_command == "inventory":
        manifest = write_inventory(args.folder)
        print(
            f"{len(manifest['files'])} ficheiros, {manifest['bytes'] / 1e6:.0f} MB, "
            f"modelos: {', '.join(manifest['models'])}"
        )
        return 0
    problems = verify(args.folder)
    for problem in problems:
        print(f"PROBLEMA: {problem}")
    if not problems:
        print(f"OK: os modelos em {args.folder} correspondem ao manifesto.")
    return 1 if problems else 0
