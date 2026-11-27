import os

import pytest

from crl_markdown.caminhos import extended, longpath, plain
from crl_markdown.page_ocr import check_ocr_models
from crl_markdown.revisions import audit_revision, create_revision
from tests.test_revisions import damaged_output  # noqa: F401 (fixture partilhada)

LONG_OUTPUT = r'C:\Users\CRL044628\eSocial\Centro de Relações Laborais - Negociação Coletiva\RNC_Dados_2026 - Cópia\2_processamento\texto'


def test_extended_path_is_idempotent_and_reversible():
    value = extended(LONG_OUTPUT)
    assert value == '\\\\?\\' + LONG_OUTPUT
    assert extended(value) == value
    assert plain(value) == LONG_OUTPUT


def test_unc_share_keeps_server_and_share():
    value = extended(r'\\servidor\partilha\texto')
    assert value == r'\\?\UNC\servidor\partilha\texto'
    assert plain(value) == r'\\servidor\partilha\texto'


def test_correction_paths_exceeded_windows_limit_before_the_fix():
    # Medida observada na estação: pasta de saída com 121 caracteres e
    # identificadores de 64 + 32 caracteres nas subpastas de correção.
    stem = '2026_BTE_28_JUR_348_46278_PortugaliaCompanhia-SNPVAC'
    old = '\\'.join([LONG_OUTPUT, '_auditoria', 'correcoes', 'x' * 64, 'y' * 32, 'cache', stem + '.docling.json'])
    assert len(LONG_OUTPUT) == 121 and len(old) > 260


@pytest.mark.skipif(os.name == 'nt', reason='fora do Windows o caminho fica inalterado')
def test_longpath_is_noop_outside_windows(tmp_path):
    assert longpath(tmp_path) == tmp_path


def test_missing_model_folder_is_reported_in_portuguese(tmp_path):
    with pytest.raises(ValueError, match='pasta de modelos indicada não existe'):
        check_ocr_models(tmp_path / 'inexistente')
    with pytest.raises(ValueError, match='não serve para OCR'):
        check_ocr_models(tmp_path)


def test_correction_works_in_output_folder_deeper_than_windows_limit(damaged_output, tmp_path):  # noqa: F811
    deep = tmp_path / ('Centro de Relações Laborais - Negociação Coletiva ' * 3).strip() / 'RNC_Dados_2026 - Cópia'
    target = longpath(deep / '2_processamento' / 'texto')
    os.makedirs(target.parent, exist_ok=True)
    os.replace(longpath(damaged_output), target)
    revision = create_revision(target, 'source.pdf', 'Revisor de ensaio')
    assert len(str(revision / 'cache' / 'source.docling.json')) > 260
    draft = revision / 'correcao.md'
    draft.write_text(draft.read_text(encoding='utf-8').replace('125,00', '-125,00'), encoding='utf-8')
    _, report = audit_revision(revision)
    assert report['quality_status'] != 'blocked'
