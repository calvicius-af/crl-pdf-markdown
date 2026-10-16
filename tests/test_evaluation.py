import json

from crl_markdown.evaluation import evaluate


def test_comparison_reports_transitions_rule_documents_and_reference_failures(tmp_path):
    baseline, candidate = tmp_path / 'before.json', tmp_path / 'after.json'
    before = {'run_id': 'before', 'status': 'concluida', 'documents': [
        {'relative_source': 'a.pdf', 'quality_status': 'review',
         'findings': [{'rule': 'STRUCTURE', 'severity': 'warning'}]}]}
    after = {'run_id': 'after', 'status': 'concluida', 'output': str(tmp_path),
             'started_at_utc': '2026-10-16T12:00:00+00:00', 'finished_at_utc': '2026-10-16T12:00:02+00:00',
             'documents': [{'relative_source': 'a.pdf', 'quality_status': 'passed', 'findings': []}]}
    baseline.write_text(json.dumps(before), encoding='utf-8')
    candidate.write_text(json.dumps(after), encoding='utf-8')
    (tmp_path / 'a.md').write_text('# Documento\n\n## CAPÍTULO II\n\n### Cláusula 4.ª\n', encoding='utf-8')
    reference = tmp_path / 'reference.json'
    reference.write_text(json.dumps({'documents': [{'stem': 'a', 'headings': ['## CAPÍTULO I']}]}), encoding='utf-8')
    result = evaluate(baseline, candidate, tmp_path / 'evaluation', reference=reference)
    assert result['comparable_complete_corpus']
    assert result['transitions'] == {'review → passed': 1}
    assert result['before']['affected_documents']['STRUCTURE'] == 1
    assert result['after']['affected_documents'] == {}
    assert result['reference_checks']['documents'][0]['status'] == 'failed'


def test_interrupted_or_incomplete_candidate_is_not_a_complete_comparison(tmp_path):
    baseline, candidate = tmp_path / 'before.json', tmp_path / 'after.json'
    before = {'run_id': 'before', 'status': 'concluida', 'documents': [
        {'relative_source': 'a.pdf', 'quality_status': 'passed', 'findings': []}]}
    after = {**before, 'run_id': 'after', 'status': 'interrompida',
             'started_at_utc': '2026-10-16T12:00:00+00:00', 'finished_at_utc': '2026-10-16T12:00:01+00:00',
             'documents': [{'relative_source': 'a.pdf', 'state': 'nao_processado'}]}
    baseline.write_text(json.dumps(before), encoding='utf-8')
    candidate.write_text(json.dumps(after), encoding='utf-8')
    assert not evaluate(baseline, candidate, tmp_path / 'evaluation')['comparable_complete_corpus']
