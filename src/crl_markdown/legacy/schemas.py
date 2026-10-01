"""Contratos de dados entre fases do pipeline (JSON Schema).

doc.json  — estrutura hierárquica de uma convenção, com offsets sobre doc.txt
anotacoes.json — codificações propostas, com confiança e método
registo_bte.jsonl — uma linha por documento adquirido (cct/recolha.py)
"""
from jsonschema import validate

SUBTIPOS = [
    "primeira_convencao",
    "revisao_global",
    "revisao_parcial",
    "revisao_parcial_com_consolidado",
    "texto_consolidado",
    "retificacao",        # AE-ALT-RECT / CCT-ALT-RECT no registo BTE
    "desconhecido",
]

TIPOS_NO = [
    "preambulo", "capitulo", "seccao", "clausula", "artigo",
    "anexo", "tabela", "regulamento", "bloco", "paragrafo",
]

_NO = {
    "type": "object",
    "required": ["id", "tipo", "rotulo", "char_start", "char_end"],
    "properties": {
        "id": {"type": "string"},
        "tipo": {"enum": TIPOS_NO},
        "rotulo": {"type": "string"},
        "char_start": {"type": "integer", "minimum": 0},
        "char_end": {"type": "integer", "minimum": 0},
        "pai": {"type": ["string", "null"]},
        "origem": {"enum": ["novo", "consolidado"]},
    },
}

DOC_SCHEMA = {
    "type": "object",
    "required": ["versao_schema", "doc_id", "tipo", "subtipo", "nos"],
    "properties": {
        "versao_schema": {"type": "string"},
        "doc_id": {"type": "string", "minLength": 1},
        "tipo": {"type": "string"},
        "subtipo": {"enum": SUBTIPOS},
        "nos": {"type": "array", "items": _NO, "minItems": 1},
    },
}


def validar_doc(doc: dict) -> None:
    validate(instance=doc, schema=DOC_SCHEMA)
