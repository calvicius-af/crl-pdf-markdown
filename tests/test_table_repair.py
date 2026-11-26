import pdfplumber
from docling_core.types.doc import (
    BoundingBox,
    DoclingDocument,
    ProvenanceItem,
    Size,
    TableCell,
    TableData,
)

from crl_markdown.table_repair import recover_grid, verify_cell_positions
from tests.pdf_sintetico import escrever_pdf, grelha


def test_drawn_grid_keeps_category_level_amount_associations(tmp_path):
    pdf = escrever_pdf(tmp_path / 'grid.pdf', [
        grelha(50, 500, [180, 80, 80], [25, 25, 25]) + [
            (55, 558, 'Categoria'), (235, 558, 'A'), (315, 558, 'B'),
            (55, 533, 'Tecnico de grau V'), (235, 533, '1250,00'), (315, 533, '1300,00'),
            (55, 508, 'Tecnico de grau IV'), (235, 508, '1100,00'), (315, 508, '1150,00'),
        ]
    ])
    with pdfplumber.open(pdf) as source:
        table = source.pages[0].find_tables()[0]
        recovered = recover_grid(source.pages[0], table)
    assert recovered['rows'] == [
        ['Categoria', 'A', 'B'], ['Tecnico de grau V', '1250,00', '1300,00'],
        ['Tecnico de grau IV', '1100,00', '1150,00']]
    assert recovered['unassigned'] == []


def test_swapped_grid_positions_are_detected_even_with_all_values_preserved(tmp_path):
    pdf = escrever_pdf(tmp_path / 'positions.pdf', [
        grelha(50, 500, [180, 80, 80], [25, 25, 25]) + [
            (55, 558, 'Categoria'), (235, 558, 'A'), (315, 558, 'B'),
            (55, 533, 'Tecnico V'), (235, 533, '1250,00'), (315, 533, '1300,00'),
            (55, 508, 'Tecnico IV'), (235, 508, '1100,00'), (315, 508, '1150,00'),
        ]])
    document = DoclingDocument(name='test')
    document.add_page(page_no=1, size=Size(width=595, height=842))
    values = [['Categoria', 'A', 'B'], ['Tecnico V', '1250,00', '1300,00'], ['Tecnico IV', '1100,00', '1150,00']]
    with pdfplumber.open(pdf) as source:
        grid = source.pages[0].find_tables()[0]
        cells = []
        for row, texts in enumerate(values):
            for col, text in enumerate(texts):
                left, top, right, bottom = grid.rows[row].cells[col]
                cells.append(TableCell(text=text, bbox=BoundingBox(l=left+1, t=top+1, r=right-1, b=bottom-1, coord_origin='TOPLEFT'),
                    start_row_offset_idx=row, end_row_offset_idx=row+1,
                    start_col_offset_idx=col, end_col_offset_idx=col+1))
        document.add_table(data=TableData(num_rows=3, num_cols=3, table_cells=cells),
            prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=50, t=575, r=390, b=500, coord_origin='BOTTOMLEFT'), charspan=(0, 0)))
        source.pages[0]._crl_tables = [grid]
        assert verify_cell_positions(source, document) == []
        cells = document.tables[0].data.table_cells
        cells[4].start_row_offset_idx, cells[4].end_row_offset_idx = 2, 3
        cells[7].start_row_offset_idx, cells[7].end_row_offset_idx = 1, 2
        findings = verify_cell_positions(source, document)
        assert len(findings) == 2
        assert all(f.rule == 'TABLE_CELL_POSITION' and f.severity == 'error' for f in findings)
        assert {f.evidence['rendered_cell'] for f in findings} == {'1250,00', '1100,00'}
        # Uma caixa imprecisa, com o valor na linha certa, não é perda de conteúdo.
        cells[4].start_row_offset_idx, cells[4].end_row_offset_idx = 1, 2
        cells[7].start_row_offset_idx, cells[7].end_row_offset_idx = 2, 3
        cells[4].bbox = cells[7].bbox.model_copy()
        findings = verify_cell_positions(source, document)
        assert len(findings) == 1 and findings[0].severity == 'info'
        assert findings[0].rule == 'TABLE_CELL_GEOMETRY'
