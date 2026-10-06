"""Contrato do registo de recolha, portado do AppCCT (9faa8fe)."""

from jsonschema import validate

ESTADOS_DESCARGA = [
    "descarregado",
    "ja_existente",
    "inalterado",
    "falhado",
    "ignorado",
    "por_descarregar",
]
ESTADOS_NOMEACAO = [
    "nomeado",
    "ja_existente",
    "por_nomear",
    "por_confirmar",
    "conflito",
    "sem_origem",
]

# Validar os campos lidos pela recolha e conservar campos adicionais dos
# registos AppCCT, incluindo estados e ordinais de nomeação.
REGISTO_SCHEMA = {
    "type": "object",
    "required": ["chave"],
    "properties": {
        "chave": {"type": "string", "minLength": 1},
        "ano": {"type": ["integer", "null"]},
        "num_bte": {"type": ["integer", "null"]},
        "descarga": {
            "type": "object",
            "properties": {
                "estado": {"enum": ESTADOS_DESCARGA},
            },
        },
        "nomeacao": {
            "type": "object",
            "properties": {
                "ordinal": {"type": ["integer", "null"], "minimum": 1},
                "estado": {"enum": ESTADOS_NOMEACAO},
            },
        },
    },
}


def validar_registo(entrada: dict) -> None:
    validate(entrada, REGISTO_SCHEMA)
