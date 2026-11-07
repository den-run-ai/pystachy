"""Check this compact evidence package without executing compilers or using the network."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def raw(name):
    data = (ROOT / name).read_bytes()
    return gzip.decompress(data) if name.endswith('.gz') else data

def read(name):
    return json.loads(raw(name))

checksums = {}
for line in (ROOT / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert name not in checksums and not name.startswith('/') and '..' not in Path(name).parts
    checksums[name] = digest
actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
          if p.is_file() and p.name != 'SHA256SUMS' and '__pycache__' not in p.parts}
assert actual == set(checksums), 'missing or unexpected packaged file'
for name, digest in checksums.items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
for item in read('provenance.json')['files']:
    assert checksums[item['path']] == item['packaged_sha256']
    assert hashlib.sha256(raw(item['path'])).hexdigest() == item['decoded_sha256']

complete = read('audit/complete-audit-review.json.gz')
inputs = read('audit/inputs.json.gz')
summary = read('audit/summary.json')
ledger = [json.loads(line) for line in raw('audit/results.jsonl.gz').splitlines()]
llvm = read('audit/llvm-verification.json.gz')
assert len(complete['rows']) == len(ledger) == len(inputs['cases']) == 4341
assert len({r['case'] for r in ledger}) == len(ledger)
assert Counter(r['category'] for r in complete['rows']) == complete['category_counts']
assert sum(v for k, v in complete['category_counts'].items() if k != 'identical_raw') == 588
records = {r['index']: r for r in ledger}
for row in complete['rows']:
    record = records[row['index']]
    assert row['case'] == record['case'] == inputs['cases'][row['index'] - 1]
    for side in ('old', 'new'):
        assert row[side + '_status'] == record[side]['status']
        assert row[side + '_ir_sha256'] == record[side]['ir_sha256']
assert summary['inputs_unchanged'] and not summary['new_rejections']
assert not summary['timeouts'] and not summary['abnormal_exits'] and not summary['missing_ir']
assert not complete['new_rejections'] and not complete['unexplained_cases']
assert len(llvm['rows']) == llvm['passed'] == 511 and not llvm['failures']
for row in llvm['rows']:
    assert row['status'] == 0 and not row['timed_out']
    assert row['ir_sha256'] == records[row['index']]['new']['ir_sha256']

identity = read('source-identity.json')
assert identity['protected_paths_unchanged']
assert identity['final_pr_head_test_merge_and_main_trees_equal']
ci = read('pr-ci/final-checks.json')
assert ci['head'] == identity['identities']['final_pr_head']['commit']
assert ci['tested_merge'] == identity['identities']['tested_pr_merge']['commit']
assert ci['tree'] == identity['identities']['merged_main']['tree']
assert len(ci['ci']['jobs']) == 16 and all(j['result'] == 'success' for j in ci['ci']['jobs'])
assert ci['lint']['detect_leaks'] == 1 and ci['lint']['result'] == 'success'
q = read('pr-ci/qualification.json')
assert q['exact_case_mode_pairs'] == 2 * q['corpus_cases'] == 8482
assert {tuple(r['modes']) for r in q['native']} == {('jit',), ('aot',)}
assert all(r['passed'] == r['expected'] and r['failed'] == 0 for r in q['native'])
assert q['gc_self']['compiler_interval'] == 5000 and q['gc_self']['result'] == 'pass'
print('PASS: file hashes, 4341 classifications/command records, 511 LLVM results, source identities and recorded PR qualification')
