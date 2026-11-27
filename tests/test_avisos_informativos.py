from crl_markdown.policies import informative, policy
from crl_markdown.quality import Finding


def test_shape_warnings_become_information_but_errors_and_other_warnings_stay():
    findings = informative([
        Finding('TABLE_SPAN', 0, 'células unidas'),
        Finding('TABLE_WIDE', 3, 'tabela larga'),
        Finding('LIST_MARKER', 0, 'sem marcador'),
        Finding('STRUCTURE', 0, 'cláusula sem corpo'),
        Finding('TABLE_OVERLAP', 0, 'sobreposição', 'error'),
    ])
    assert [f.severity for f in findings] == ['info', 'info', 'info', 'warning', 'error']
    assert policy()['versao'] == '2026-11-27.1'
