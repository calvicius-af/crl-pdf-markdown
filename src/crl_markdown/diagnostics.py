"""Explicações autónomas com detalhe técnico conservado para assistência."""

import errno
import json
import platform
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from .pipeline import atomic_write


def safe_detail(text: str) -> str:
    """Retira credenciais de URLs e segredos explícitos; não recolhe outros dados."""
    text = re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[credenciais omitidas]@", text)
    return re.sub(r"(?i)(token|password|api_key|authorization)(\s*[:=]\s*)([^\s,;]+)",
                  r"\1\2[omitido]", text)


def explain(error: BaseException) -> dict:
    detail = safe_detail(str(error))
    lowered = detail.lower()
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        code, action = "CRL-ESPACO", (
            "Não há espaço livre suficiente. Peça ao apoio informático para libertar espaço "
            "na pasta de saída ou escolha uma unidade local com espaço e tente novamente."
        )
    elif isinstance(error, PermissionError) or (
            isinstance(error, OSError) and error.errno == errno.EROFS):
        code, action = "CRL-PERMISSOES", (
            "Escolha uma pasta local onde possa guardar ficheiros, por exemplo Documentos. "
            "Feche o ficheiro aberto no Excel ou noutro programa e tente novamente. "
            "Se continuar, entregue este relatório ao apoio informático."
        )
    elif isinstance(error, FileExistsError):
        code, action = "CRL-SAIDA-EXISTENTE", (
            "Escolha uma pasta de saída nova. Se pretende refazer a extração, guarde primeiro "
            "as correções manuais e só depois selecione Substituir saídas existentes."
        )
    elif isinstance(error, (ImportError, ModuleNotFoundError)):
        code, action = "CRL-INSTALACAO", (
            "Abra a aplicação pelo lançador CRL, para usar o ambiente instalado. "
            "Se não abrir, execute novamente Instalar_CRL.bat a partir do pacote offline "
            "completo. Conserve este relatório se o problema continuar."
        )
    elif any(word in lowered for word in ("model", "hugging", "artifacts", "offline")):
        code, action = "CRL-MODELOS", (
            "No campo Pasta de modelos, escolha a pasta modelos do pacote instalado. "
            "Mantenha Modelos locais / offline selecionado. Se faltar essa pasta, "
            "obtenha uma cópia completa do pacote junto do apoio informático."
        )
    elif isinstance(error, TimeoutError) or any(
            word in lowered for word in ("timeout", "tempo máximo", "timed out")):
        code, action = "CRL-TEMPO", (
            "Experimente converter apenas o PDF indicado. Feche programas pesados. "
            "O apoio informático pode aumentar o tempo máximo sem mudar de extrator."
        )
    elif isinstance(error, FileNotFoundError):
        code, action = "CRL-FICHEIRO", (
            "Use o botão Pasta ou PDF para selecionar uma localização que exista. "
            "Se estiver numa unidade partilhada, confirme que consegue abri-la no Explorador."
        )
    else:
        code, action = "CRL-OPERACAO", (
            "Confira a entrada e a pasta de saída indicadas neste relatório. "
            "Tente novamente com um só documento numa pasta nova. Se continuar, "
            "entregue este relatório ao apoio informático; não precisa de alterar código."
        )
    return {"code": code, "problem": detail, "action": action,
            "error_type": type(error).__name__}


def save_failure(error: BaseException, folder: Path, context: str) -> Path:
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    data = {**explain(error), "context": safe_detail(context), "date_utc": identifier,
            "python": sys.version, "platform": platform.platform(),
            "traceback": safe_detail("".join(traceback.format_exception(error)))}
    target = folder / f"falha-{identifier}.md"
    atomic_write(target.with_suffix(".json"), json.dumps(data, ensure_ascii=False, indent=2))
    atomic_write(target, f"# A operação não terminou\n\nCódigo: {data['code']}\n\n"
                 f"Operação: {context}\n\n## O que aconteceu\n\n{data['problem']}\n\n"
                 f"## O que fazer agora\n\n{data['action']}\n\n"
                 "## Se continuar\n\nEntregue este relatório e o JSON com o mesmo nome ao apoio informático.\n\n"
                 "## Para o apoio informático\n\n"
                 f"O ficheiro JSON com o mesmo nome conserva o erro técnico e o ambiente.\n"
                 f"Python: {sys.executable}\n")
    return target
