"""Read-only binding/inventory and synthetic diagnostic tests; no compiler invocation."""
import ast
import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
path = HERE / 'compare_corpus_current.py'
spec = importlib.util.spec_from_file_location('comparison_current', path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

old = ast.parse((HERE / 'compare_corpus.py').read_text())
new = ast.parse(path.read_text())
unchanged = ['snapshot', 'plan_cases', 'ProcessRunner', 'retain', 'validate']
for name in unchanged:
    a = next(n for n in old.body if getattr(n, 'name', None) == name)
    b = next(n for n in new.body if getattr(n, 'name', None) == name)
    assert ast.dump(a) == ast.dump(b), name

homes = {'main': Path('/baseline'), 'candidate': Path('/candidate')}
files = {'lib/example.py': 'samehash'}
manifests = {role: {'files': dict(files)} for role in homes}


def compare(a, b, sa=b'', sb=b''):
    return m.diagnostic_comparison({'main': (sa, a), 'candidate': (sb, b)}, homes, manifests)


assert compare(b'', b'') == (True, True, None)
a = b'/baseline/lib/example.py:7: error: expected rejection\n'
b = b'/candidate/lib/example.py:7: error: expected rejection\n'
result = compare(a, b)
assert result[:2] == (False, True) and result[2]['relative_source'] == 'lib/example.py'
assert compare(a, b.replace(b':7:', b':8:')) == (False, False, None)
assert compare(a, b.replace(b'rejection', b'difference')) == (False, False, None)
assert compare(a, b.replace(b'example', b'other')) == (False, False, None)
assert compare(a, b, b'unexpected', b'') == (False, False, None)
assert compare(a + b, b + b) == (False, False, None)
assert compare(a, b.replace(b'/candidate/', b'/elsewhere/')) == (False, False, None)
assert compare(a.replace(b'expected rejection', b'/baseline/inside-message'),
               b.replace(b'expected rejection', b'/candidate/inside-message')) == (False, False, None)
assert compare(a.replace(b'/lib/', b'/lib/../lib/'),
               b.replace(b'/lib/', b'/lib/../lib/')) == (False, False, None)
manifests['candidate']['files']['lib/example.py'] = 'differenthash'
assert compare(a, b) == (False, False, None)

main = HERE.parent / 'main1000'
candidate = HERE.parent / 'pystachy'
env = dict(os.environ, LC_ALL='C')
mp = m.plan_cases(main, env)
cp = m.plan_cases(candidate, env)
report = {
    'status': 'passed',
    'scope': 'Read-only source inventory, unchanged-function AST comparison, synthetic diagnostic cases, and fresh main build binding; no compiler invocation.',
    'harness_sha256': m.digest(path),
    'self_check_sha256': m.digest(Path(__file__)),
    'historical_harness_sha256': m.digest(HERE / 'compare_corpus.py'),
    'unchanged_functions': unchanged,
    'synthetic_diagnostic_checks': 11,
    'main_plan': len(mp),
    'candidate_plan': len(cp),
    'candidate_programs': sum(x['expected_returncode'] == 0 for x in cp),
    'candidate_rejections': sum(x['expected_returncode'] == 1 for x in cp),
    'added_cases': sorted({x['case'] for x in cp} - {x['case'] for x in mp}),
    'removed_cases': sorted({x['case'] for x in mp} - {x['case'] for x in cp}),
}
proof = HERE / 'bootstrap-main1000/bootstrap.json'
record = json.loads(proof.read_text())
report['main_build_descriptors'] = m.validate_build(main, m.identity(main), record, proof.parent / 'bootstrap.log')
m.save(HERE / 'comparison-current-harness-review.json', report)
print(json.dumps(report, indent=2))
