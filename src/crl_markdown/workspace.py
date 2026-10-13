"""Árvore RNC para dados; o código e o ambiente Python ficam separados."""

from importlib.resources import files
from pathlib import Path

from .pipeline import atomic_write

FOLDERS = (
    "0_gestao/roteiro", "0_gestao/livro_codigos", "0_gestao/catalogo",
    "0_gestao/vocabularios", "0_gestao/atas", "0_gestao/procedimentos",
    "1_fontes/indices_bte", "1_fontes/bte_completo", "1_fontes/externas",
    "1_fontes/irct/convencoes/PRI", "1_fontes/irct/convencoes/SPE",
    "1_fontes/irct/convencoes/APU", "1_fontes/irct/portarias_extensao",
    "1_fontes/irct/acordos_adesao", "1_fontes/irct/acordaos",
    "2_processamento/texto", "2_processamento/validacao", "2_processamento/recolha_original",
    "3_analise/master", "3_analise/mqex", "3_analise/comparacoes",
    "3_analise/logs_integracao", "3_analise/revisao_textual",
    "3_analise/corpus_aprovado", "4_temas", "5_redacao", "6_relatorio",
    "7_divulgacao", "9_arquivo",
)


def initialize(root: Path):
    """Inicializar a partir de recursos instalados, conservando edições da equipa."""
    root = Path(root)
    for folder in FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
    resources = files("crl_markdown").joinpath("vocabularios")
    for source in resources.iterdir():
        if not source.is_file() or not source.name.endswith((".csv", ".json")):
            continue
        target = root / "0_gestao/vocabularios" / source.name
        if not target.exists():
            atomic_write(target, source.read_text(encoding="utf-8-sig"))
    return root
