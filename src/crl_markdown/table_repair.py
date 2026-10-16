"""Reparação auxiliar de grelhas desenhadas no PDF, com prova de conservação."""

import re
from collections import Counter

from .quality import Finding


def characters(text):
    return Counter(c for c in text if not c.isspace())


def _inside(obj, box):
    if obj.get('object_type') != 'char':
        return False
    x, y = (obj['x0'] + obj['x1']) / 2, (obj['top'] + obj['bottom']) / 2
    return box[0] <= x < box[2] and box[1] <= y < box[3]


def recover_grid(page, table):
    """Ler cada região uma vez; células unidas não repetem conteúdo."""
    rows, seen = [], set()
    for row in table.rows:
        values = []
        for box in row.cells:
            if box is None or box in seen:
                values.append('')
                continue
            seen.add(box)
            area = page.filter(lambda obj, box=box: _inside(obj, box))
            values.append(area.extract_text(x_tolerance=1, y_tolerance=1,
                                           line_dir_rotated='ltr', char_dir_rotated='btt') or '')
        rows.append(values)
    original_chars = [c for c in page.chars if _inside(c, table.bbox)]
    original = ''.join(c['text'] for c in original_chars)
    unassigned = [c for c in original_chars if not c['text'].isspace()
                  and not any(_inside(c, box) for box in seen)]
    extracted = ''.join(c for row in rows for c in row) + ''.join(c['text'] for c in unassigned)
    if characters(original) != characters(extracted):
        return None
    # Separar linhas fundidas só quando categorias e valores têm o mesmo
    # número de linhas. Se não há correspondência inequívoca, manter a célula.
    expanded = []
    for row in rows:
        parts = [cell.splitlines() for cell in row]
        numeric = [len(p) for p in parts if len(p) > 1 and
                   all(re.fullmatch(r'[\d\s.,*]+|\(\*+\)', v.strip()) for v in p)]
        count = numeric[0] if numeric and len(set(numeric)) == 1 else 1
        if count > 1 and all(len(p) in {0, 1, count} for p in parts) and any(
            len(p) == count and any(re.search(r'[A-Za-zÀ-ÿ]', v) for v in p) for p in parts
        ):
            for i in range(count):
                expanded.append([p[i] if len(p) == count else p[0] if p and i == 0 else '' for p in parts])
        else:
            expanded.append([' / '.join(p) for p in parts])
    gaps = []
    for char in unassigned:
        gaps.append({'text': char['text'], 'bbox': [char['x0'], char['top'], char['x1'], char['bottom']]})
    return {'rows': expanded, 'unassigned': gaps}


def recover_tables(pdf, document):
    """Só substituir uma grelha densa defeituosa por linhas/colunas verificadas."""
    import pdfplumber

    result = {}
    dense = [t for t in document.tables if t.data.num_cols > 8 and len(t.prov) == 1]
    if not dense:
        return result
    with pdfplumber.open(pdf) as source:
        pages = {}
        for item in dense:
            prov = item.prov[0]
            if prov.page_no not in pages:
                page = source.pages[prov.page_no - 1].dedupe_chars()
                pages[prov.page_no] = page, page.find_tables()
            page, tables = pages[prov.page_no]
            box = prov.bbox.to_top_left_origin(page.height)
            candidates = []
            for table in tables:
                x0, y0, x1, y1 = table.bbox
                intersection = max(0, min(x1, box.r) - max(x0, box.l)) * max(0, min(y1, box.b) - max(y0, box.t))
                union = (x1-x0)*(y1-y0) + (box.r-box.l)*(box.b-box.t) - intersection
                if union > 0 and intersection / union > .8 and len(table.rows) > item.data.num_rows + 2:
                    candidates.append(table)
            if len(candidates) != 1:
                continue
            recovered = recover_grid(page, candidates[0])
            if recovered:
                rows = recovered['rows']
                # O conteúdo fora da grelha é conservado em linha separada,
                # sem atribuir categoria/nível por aproximação. Continua bloqueado.
                for gap in recovered['unassigned']:
                    rows.append([gap['text']] + [''] * (len(rows[0]) - 1))
                result[item.self_ref] = {**recovered, 'page': prov.page_no,
                    'bbox': list(candidates[0].bbox), 'source_shape': [item.data.num_rows, item.data.num_cols],
                    'repaired_shape': [len(rows), len(rows[0])], 'engine': 'pdfplumber_drawn_grid',
                    'character_conservation': True}
    return result


def verify_cell_positions(pdf_document, document):
    """Verificar a associação geométrica quando as duas grelhas são comparáveis."""
    findings = []
    for table in document.tables:
        if len(table.prov) != 1:
            continue
        prov = table.prov[0]
        page = pdf_document.pages[prov.page_no - 1]
        box = prov.bbox.to_top_left_origin(page.height)
        candidates = []
        for grid in getattr(page, '_crl_tables', []):
            x0, y0, x1, y1 = grid.bbox
            overlap = max(0, min(x1, box.r) - max(x0, box.l)) * max(0, min(y1, box.b) - max(y0, box.t))
            union = (x1-x0)*(y1-y0) + (box.r-box.l)*(box.b-box.t) - overlap
            if (union > 0 and overlap / union > .8 and len(grid.rows) == table.data.num_rows
                    and len(grid.rows[0].cells) == table.data.num_cols):
                candidates.append(grid)
        if len(candidates) != 1:
            continue
        grid = candidates[0]
        for cell in table.data.table_cells:
            if cell.bbox is None or cell.row_span != 1 or cell.col_span != 1 or not cell.text.strip():
                continue
            row, col = cell.start_row_offset_idx, cell.start_col_offset_idx
            expected = grid.rows[row].cells[col]
            if expected is None:
                continue
            actual = cell.bbox.to_top_left_origin(page.height)
            overlap = max(0, min(expected[2], actual.r) - max(expected[0], actual.l)) * max(
                0, min(expected[3], actual.b) - max(expected[1], actual.t))
            area = (actual.r-actual.l)*(actual.b-actual.t)
            if area > 0 and overlap / area < .2:
                findings.append(Finding('TABLE_CELL_POSITION', 0,
                    f'Página {prov.page_no}: célula na linha {row+1}, coluna {col+1} '
                    'não corresponde à região da grelha desenhada no PDF. Conferir categoria/nível/valor.',
                    'error', page=prov.page_no, node=table.self_ref, bbox=tuple(actual.as_tuple())))
    return findings
