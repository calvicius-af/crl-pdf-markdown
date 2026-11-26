import pytest
from docling_core.types.doc import DocItemLabel, DoclingDocument

from crl_markdown.document import prepare
from crl_markdown.legacy import sanidade
from crl_markdown.legacy.extractor import estruturar
from crl_markdown.tipologias import perfil_documental


@pytest.mark.parametrize('name', [
    '2026_BTE_17_PE_188_0201-2026-1_26968_X-Y',
    '2026_BTE_28_PCT_335_0306-2026-1_30350_PCT',
    '2026_BTE_02_AA_033_16517_X-Y',
    '2026_BTE_28_JUR_348_46278_X-Y',
    '2026_BTE_03_APU_034_ACT_ACEP1-2026_X-Y',
    '2026_BTE_09_APU_092_ACEP-ALT_ACEP322-2015_X-Y',
])
def test_deposit_not_required_outside_private_conventions(name):
    doc, text = estruturar('Publicação autónoma integral.\n', name,
                          subtipo=perfil_documental(name))
    warnings = sanidade.verificar(doc, text)
    assert not any('depósito' in w for w in warnings)
    if doc['subtipo'] != 'convencao_publica':
        assert not any('nenhuma cláusula' in w for w in warnings)


def test_unknown_and_private_convention_still_detect_truncation():
    for profile in ['desconhecido', 'convencao_privada']:
        doc, text = estruturar('Documento truncado.', 'exemplo', subtipo=profile)
        warnings = sanidade.verificar(doc, text)
        assert any('depósito' in w for w in warnings)
        assert any('nenhuma cláusula' in w for w in warnings)


def test_explicit_catalog_metadata_overrides_ambiguous_filename():
    assert perfil_documental('exemplo', {'familia': 'acordao'}) == 'acordao'
    assert perfil_documental('exemplo', {'tipo': 'ACEP-ALT', 'ambito_documental': 'APU'}) == 'alteracao_publica'
    assert perfil_documental('2026_BTE_01_PE_exemplo', {'familia': 'acordao', 'tipo': 'JUR'}) == 'acordao'
    assert perfil_documental('exemplo', {'familia': 'convencao', 'tipo': 'ACT',
                            'ambito_documental': 'APU', 'operacao_documental': 'alteracao'}) == 'alteracao_publica'


def test_elimination_command_is_a_valid_clause_body():
    doc, text = estruturar('Cláusula 16.ª\nEliminar\nCláusula 17.ª\n1- Texto mantido.', 'alt')
    assert not sanidade.clausulas_sem_corpo(doc, text)


def test_initial_articulated_text_does_not_remain_inside_preamble_maxqda():
    doc = DoclingDocument(name='exemplo')
    doc.add_text(label=DocItemLabel.TEXT, text='As partes acordam no presente instrumento.')
    doc.add_heading(text='Âmbito e vigência', level=1)
    doc.add_heading(text='Cláusula 3.ª', level=1)
    doc.add_text(label=DocItemLabel.TEXT, text='1- Compete à comissão interpretar o acordo.')
    doc.add_heading(text='CAPÍTULO II', level=1)
    doc.add_heading(text='Admissões', level=1)
    doc.add_heading(text='Cláusula 4.ª', level=1)
    doc.add_text(label=DocItemLabel.TEXT, text='1- São admitidos os trabalhadores.')
    prepared = prepare(doc, 'exemplo')
    assert '## Âmbito e vigência\n\n### Cláusula 3.ª' in prepared.markdown
    assert '## CAPÍTULO II - Admissões\n\n### Cláusula 4.ª' in prepared.markdown
    assert 'CAPÍTULO I\n' not in prepared.markdown
    assert not any(f.rule == 'RENDER_CONTENT' for f in prepared.findings)


def test_new_chapter_closes_section_and_clause_maxqda():
    doc = DoclingDocument(name='exemplo')
    for title in ['CAPÍTULO V', 'Cláusula 25.ª']:
        doc.add_heading(text=title, level=1)
    doc.add_text(label=DocItemLabel.TEXT, text='1- É proibido ao empregador diminuir a retribuição.')
    for title in ['CAPÍTULO VI', 'Prestação do trabalho', 'SECÇÃO I', 'Princípios gerais', 'Cláusula 26.ª']:
        doc.add_heading(text=title, level=1)
    doc.add_text(label=DocItemLabel.TEXT, text='1- O trabalho será regulamentado.')
    prepared = prepare(doc, 'exemplo')
    assert '### Cláusula 25.ª' in prepared.markdown
    assert '## CAPÍTULO VI - Prestação do trabalho' in prepared.markdown
    assert '### SECÇÃO I - Princípios gerais\n\n#### Cláusula 26.ª' in prepared.markdown
    nodes = prepared.structure['nos']
    clause = next(n for n in nodes if n['tipo'] == 'clausula' and '25' in n['rotulo'])
    assert 'CAPÍTULO VI' not in prepared.structured_text[clause['char_start']:clause['char_end']]
    assert not any(f.rule == 'RENDER_CONTENT' for f in prepared.findings)
