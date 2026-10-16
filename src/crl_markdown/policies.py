"""Identidade da política e aplicabilidade, sem desativar controlos de conteúdo."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

PROFILE_PATH = Path(__file__).with_name('vocabularios') / 'perfis_auditoria.json'


def policy():
    return json.loads(PROFILE_PATH.read_text(encoding='utf-8'))


def applicability(profile):
    profiles = policy()['perfis']
    return profiles.get(profile, profiles['desconhecido'])


@lru_cache(maxsize=1)
def _code_fingerprint():
    root = Path(__file__).parent
    names = ['audit.py', 'document.py', 'quality.py', 'policies.py', 'table_repair.py',
             'pipeline.py', 'textrepair.py', 'tipologias.py', 'legacy/sanidade.py',
             'legacy/extractor.py', 'legacy/extractor_docling.py', 'legacy/auditoria.py',
             'legacy/mobiliario.py', 'legacy/completude.py']
    digest = hashlib.sha256()
    for name in names:
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def fingerprint():
    digest = hashlib.sha256(_code_fingerprint().encode())
    digest.update(PROFILE_PATH.read_bytes())
    digest.update(PROFILE_PATH.with_name('tipologias_documentais.json').read_bytes())
    return digest.hexdigest()


@lru_cache(maxsize=8)
def _registry_profiles(path, modified, size):
    records = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            record = json.loads(line)
            name = Path(record.get('nomeacao', {}).get('nome', '')).stem
            records.setdefault(name, []).append(record)
    return records


def model_fingerprint(models):
    if models is None:
        return None
    from .models import MANIFEST
    manifest = Path(models) / MANIFEST
    return hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else 'unverified'


def profile_context(pdf):
    """Preferir o catálogo selecionado; o nome canónico é o fallback explícito."""
    from .tipologias import perfil_documental

    pdf = Path(pdf)
    for parent in pdf.parents:
        registry = parent / '0_gestao/catalogo/registo_bte.jsonl'
        if registry.is_file():
            stat = registry.stat()
            matches = _registry_profiles(str(registry), stat.st_mtime_ns, stat.st_size).get(pdf.stem, [])
            if len(matches) == 1:
                return perfil_documental(pdf.stem, matches[0]), 'catalogo_rnc'
            if matches:
                raise ValueError(f'Perfil documental ambíguo no catálogo: {pdf.name}')
            break
    return perfil_documental(pdf.stem), 'nome_canonico'
