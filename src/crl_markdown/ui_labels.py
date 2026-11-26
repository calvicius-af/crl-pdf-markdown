"""Rótulos portugueses; os códigos continuam disponíveis para diagnóstico."""

RULES = {
    'AMOUNTS': 'Montantes', 'CRITICAL_SYMBOLS': 'Sinais e símbolos críticos',
    'COMPLETENESS': 'Completude do conteúdo', 'COMPLETENESS_UNAVAILABLE': 'Completude não verificada',
    'REFERENCE_EMPTY': 'Referência sem texto', 'STRUCTURE': 'Estrutura documental',
    'SIGNED_VALUES_UNAVAILABLE': 'Sinais numéricos não verificados',
    'TABLE_AUDIT': 'Conferência de tabelas', 'TABLE_AUDIT_UNAVAILABLE': 'Tabelas não verificadas',
    'TABLES_MISSING': 'Tabelas em falta', 'TABLE_SPAN': 'Células unidas',
    'TABLE_WIDE': 'Tabela larga', 'TABLE_EMPTY': 'Tabela vazia',
    'TABLE_OVERLAP': 'Células sobrepostas', 'TABLE_GRID_GAP': 'Lacunas na grelha',
    'TABLE_CELL_POSITION': 'Posição das células', 'TABLE_CELL_GEOMETRY': 'Geometria das células',
    'TABLE_RECONSTRUCTED': 'Tabela reconstruída', 'TABLE_AS_TEXT': 'Tabela apresentada como texto',
    'IMAGE': 'Imagem por conferir', 'LIST_MARKER': 'Marcadores de lista',
    'LEGAL_LIST_BULLET': 'Numeração jurídica convertida em lista',
    'CLAUSE_TITLE_SPLIT': 'Título de cláusula separado', 'EMPTY': 'Documento vazio',
    'UNICODE': 'Caracteres especiais', 'MD001': 'Níveis dos títulos', 'MD033': 'Conteúdo HTML',
    'MD056': 'Número de colunas da tabela', 'RENDER_CONTENT': 'Conteúdo após formatação',
    'TABLE_UNPARSED': 'Tabela não interpretada',
}
PROFILES = {
    'desconhecido': 'Não identificado', 'convencao_privada': 'Convenção privada',
    'convencao_publica': 'Convenção pública', 'alteracao_privada': 'Alteração de convenção privada',
    'alteracao_publica': 'Alteração de convenção pública', 'portaria': 'Portaria',
    'adesao': 'Acordo de adesão', 'acordao': 'Acórdão', 'aviso': 'Aviso',
    'retificacao': 'Retificação', 'cessacao_vigencia': 'Cessação de vigência',
    'deliberacao_comissao_paritaria': 'Deliberação de comissão paritária',
}
FAMILIES = {'convencoes': 'Convenções', 'portarias_extensao': 'Portarias de extensão',
            'acordos_adesao': 'Acordos de adesão', 'acordaos': 'Acórdãos',
            'cessacoes_vigencia': 'Cessações de vigência', 'avisos': 'Avisos', '.': 'Documentos na raiz'}


def rule_label(code):
    return f'{RULES.get(code, code.replace("_", " ").capitalize())} ({code})'


def family(document):
    from pathlib import Path
    parts = Path(document['relative_source']).parts
    return parts[0] if len(parts) > 1 else '.'
