"""Classify the retained 2026-11-07 IR oracle evidence without recompiling.

This never changes either checkout or the retained compiler outputs.  It validates
specific, reversible transformations, then requires byte identity of the complete
IR.  It does not generally replace paths, remove instructions, or ignore numbering.
"""
from bisect import bisect_right
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import stat
import subprocess


BASE = Path('/workspace/scratch/9c9ef915af51')
OLD = BASE / 'baseline'
NEW = BASE / 'pystachy'
EVIDENCE = Path('/tmp/pystachy-irsame.w8v9sp')
LOG = BASE / 'irsame-full.log'
REPORT = BASE / 'irsame-classification.json'
CASE_MAP = BASE / 'irsame-case-map.json'
INITIAL_CANDIDATE = '93c1284cafb454ee1531c422012ea9181bcbf0cd'
OLD_LIB = str(OLD / 'lib') + '/'
NEW_LIB = str(NEW / 'lib') + '/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root, text=True).strip()


def manifest(root):
    result = {}
    for p in sorted(root.rglob('*')):
        if p.is_file():
            result[str(p.relative_to(root))] = {
                'sha256': sha(p.read_bytes()),
                'bytes': p.stat().st_size,
                'mode': oct(stat.S_IMODE(p.stat().st_mode)),
                'symlink': p.is_symlink(),
            }
    return result


old_lib = manifest(OLD / 'lib')
new_lib = manifest(NEW / 'lib')
old_tree = git(OLD, 'rev-parse', 'HEAD:lib')
new_tree = git(NEW, 'rev-parse', 'HEAD:lib')
assert old_tree == new_tree
assert set(old_lib) <= set(new_lib)
assert all(old_lib[n] == new_lib[n] for n in old_lib)
extras = sorted(set(new_lib) - set(old_lib))
assert extras == ['__pycache__/_pystachy_bytescan.cpython-313.pyc'], extras
assert len(old_lib) == 90
assert len([n for n in old_lib if n.endswith('.py')]) == 87


def source_location(rel, line=None):
    """Only acknowledge locations in the proven identical source files."""
    assert rel in old_lib and rel.endswith('.py'), rel
    if line is not None:
        assert 1 <= int(line) <= len((OLD / 'lib' / rel).read_text().splitlines()), (rel, line)


cases = ['pystachy.py', 'runtime.py']
for pattern in (
    'tests/programs/*/*.py', 'tests/deviations/*.py', 'bench/*.py',
    'bench/pyperformance/*.py', 'tests/ir/*.py', 'tests/errors/*/*.py',
):
    cases += sorted(str(p.relative_to(NEW)) for p in NEW.glob(pattern) if p.is_file())
assert len(cases) == 4245, len(cases)
assert {int(p.name) for p in EVIDENCE.iterdir() if p.is_dir()} == set(range(1, 4246))
log_text = LOG.read_text()
log_changed = re.findall(r'^DIFF (.+)$', log_text, re.M)

# variables.py:774-776 and :810-812 generate exactly this ImportError text.
# The replacement is confined to its library-file location in an LLVM string
# global; the symbol, byte counts, message text and all other bytes must agree.
IMPORT_PATH = re.compile(
    r'(?m)^(@s\.\d+ = private unnamed_addr global [^\n]* c"cannot import name '
    r"'[^'\"\n]+' from '[^'\"\n]+' \("
    r')' + re.escape(OLD_LIB) + r'([A-Za-z0-9_./-]+\.py)(\)\\00"\}, align 8)$'
)
PREFIX_PATH = re.compile(
    r'(?m)^(@s\.\d+ = private unnamed_addr global [^\n]* c")'
    + re.escape(str(OLD)) + r'(\\00"\}, align 8)$'
)
PREFIX_CASES = {
    'tests/programs/library/lib_gettext.py': '@s.155',
    'tests/programs/library/sys_prefix.py': '@s.2',
}

FUNCTION = re.compile(r'(?ms)^define [^\n@]*@(?P<name>[^ (]+)\([^\n]*\).*?^}')
LIST_LOAD = re.compile(
    r'(?m)^  (?P<field>%t\d+) = getelementptr inbounds \{i64, i64, ptr\}, ptr (?P<seq>[^,\n]+), i64 0, i32 2\n'
    r'  (?P<data>%t\d+) = load ptr, ptr (?P=field)\n'
    r'  (?P<elem>%t\d+) = getelementptr inbounds i64, ptr (?P=data), i64 (?P<idx>[^\n]+)\n'
    r'  (?P<res>%t\d+) = load i64, ptr (?P=elem)\n'
)
ASCII_INVOKE = re.compile(
    r'(?m)^(  (?P<res>%t\d+) = )invoke ptr @pys_ascii\(ptr (?P<arg>%t\d+)\) '
    r'to label %(?P<cont>L\d+) unwind label %(?P<handler>L\d+)\n(?P=cont):\n'
)

# Every additional unwind edge was reviewed against its surrounding preexisting
# invokes and the corresponding source try.  These are artifact-specific anchors,
# not a rule that would accept an arbitrary newly added exception edge.
ASCII_SITES = {
    ('tests/programs/library/json_scanner.py', 'f.show', '%t28'): {
        'handler': 'L6', 'source_line': 11,
        'source_context': 'show(): json.loads/dumps and ascii share its JSONDecodeError try',
    },
    ('tests/programs/library/lib_io_textiowrapper.py', 'main.init', '%t1335'): {
        'handler': 'L1312', 'source_line': 332,
        'source_context': 'ascii(t.read()) shares the preceding read and writes in the UnicodeDecodeError try',
    },
    ('tests/programs/library/lib_urllib_parse.py', 'main.init', '%t2086'): {
        'handler': 'L2080', 'source_line': 249,
        'source_context': 'ascii(url) and urlsplit(url) share this ValueError try',
    },
    ('tests/programs/library/lib_urllib_parse.py', 'f.u', '%t25'): {
        'handler': 'L8', 'source_line': 40,
        'source_context': 'return ascii(unquote(...)) shares unquote\'s UnicodeError/LookupError/TypeError try',
    },
    ('tests/deviations/json_invalid_utf8.py', 'f.main', '%t68'): {
        'handler': 'L51', 'source_line': 24,
        'source_context': 'first ascii(json.dumps(...)) in the inner JSONDecodeError try, inside finally cleanup',
    },
    ('tests/deviations/json_invalid_utf8.py', 'f.main', '%t76'): {
        'handler': 'L51', 'source_line': 24,
        'source_context': 'second ascii(json.dumps(...)) in the same inner JSONDecodeError try',
    },
}
seen_ascii = set()


def explain_diagnostic(old, new):
    """Reconcile the 13 conservatively unnormalized diagnostics, location only."""
    changes = []
    def replace(m):
        rel, line = m['file'], m['line']
        source_location(rel, line)
        changes.append({'source_file': rel, 'source_line': int(line), 'context': m['context']})
        return m['context'] + 'lib/' + rel + ':' + line
    start = re.compile(
        r'(?m)(?P<context>^)' + re.escape(OLD_LIB)
        + r'(?P<file>[A-Za-z0-9_./-]+\.py):(?P<line>\d+)(?=: error:)'
    )
    context = re.compile(
        r'(?P<context> for the call at )' + re.escape(OLD_LIB)
        + r'(?P<file>[A-Za-z0-9_./-]+\.py):(?P<line>\d+)'
    )
    restored = context.sub(replace, start.sub(replace, old))
    assert changes and restored == new
    assert OLD_LIB not in restored
    return changes


def explain_ir(name, old, new):
    path_changes = []
    bounds = []
    ascii_changes = []

    def replace_import(m):
        source_location(m[2])
        after = m[1] + NEW_LIB + m[2] + m[3]
        assert after + '\n' in new
        path_changes.append({
            'kind': 'generated_import_error_location', 'source_file': m[2],
            'old_line': m[0], 'new_line': after,
        })
        return after

    prior = IMPORT_PATH.sub(replace_import, old)

    def replace_prefix(m):
        assert name in PREFIX_CASES and m[0].startswith(PREFIX_CASES[name] + ' = ')
        after = m[1] + str(NEW) + m[2]
        assert after + '\n' in new
        path_changes.append({
            'kind': 'compiler_installation_prefix', 'old_line': m[0], 'new_line': after,
            'reason': 'builtins.py:141-144 emits self.prefix; driver.py:108 derives it from this compiler\'s lib directory',
        })
        return after

    prior = PREFIX_PATH.sub(replace_prefix, prior)
    old_functions = {m['name']: m[0] for m in FUNCTION.finditer(prior)}
    assert len(old_functions) == len(list(FUNCTION.finditer(prior)))
    assert set(old_functions) == {m['name'] for m in FUNCTION.finditer(new)}

    def restore_function(m):
        symbol, current = m['name'], m[0]
        previous = old_functions[symbol]

        def restore_load(v):
            call = f"  {v['res']} = call i64 @pys_list_get(ptr {v['seq']}, i64 {v['idx']})\n"
            if call not in previous:
                return v[0]  # A preexisting sequence-loop/unpacking load stays unchanged.
            assert previous.count(call) == 1
            bounds.append({
                'function': symbol, 'old_call': call.rstrip(),
                'new_instructions': v[0].splitlines(),
                'raw_llvm_line_delta': 3,
            })
            return call

        current = LIST_LOAD.sub(restore_load, current)
        inserted = []
        sites = []

        def restore_ascii(v):
            call = f"  {v['res']} = call ptr @pys_ascii(ptr {v['arg']})\n"
            if call not in previous:
                return v[0]
            key = (name, symbol, v['res'])
            assert key in ASCII_SITES, key
            expected = ASCII_SITES[key]
            assert v['handler'] == expected['handler']
            assert re.search(r'(?m)^' + v['handler'] + r':\n  %t\d+ = landingpad ', previous)
            assert re.search(r'unwind label %' + v['handler'] + r'\b', previous)
            # Its new continuation is used only by this invoke.  Removing the
            # immediate label really rejoins the original block, without discarding
            # any predecessor, phi edge, or branch target.
            assert len(re.findall(r'%' + v['cont'] + r'\b', current)) == 1
            inserted.append(int(v['cont'][1:]))
            record = dict(expected, function=symbol, old_call=call.rstrip(),
                          new_invoke=v[0].splitlines()[0], continuation=v['cont'])
            sites.append(record)
            seen_ascii.add(key)
            return call

        current = ASCII_INVOKE.sub(restore_ascii, current)
        if inserted:
            inserted.sort()
            renamed = {}
            def renumber(v):
                kind = v['kind'] or 'L'
                number = int(v['number'] or v['label_number'])
                assert number not in inserted
                after = number - bisect_right(inserted, number)
                before_token = ('%' if v['kind'] else '') + kind + str(number)
                after_token = ('%' if v['kind'] else '') + kind + str(after)
                if before_token != after_token:
                    renamed[before_token] = after_token
                return after_token + (':' if v['label_number'] else '')
            # gen_eh_ir shares one monotonically increasing IFn.n for newly
            # inserted continuation labels and later exception temporaries.
            # Undo only the six verified insertions' numeric offsets.  Literal
            # constants, metadata, slots, function names and all other text stay.
            token = re.compile(r'%(?P<kind>[tL])(?P<number>\d+)(?![A-Za-z0-9_.$])|^(?:L(?P<label_number>\d+)):', re.M)
            current = token.sub(renumber, current)
            assert current == previous, (name, symbol, 'ASCII reconstruction differs')
            ascii_changes.append({
                'function': symbol, 'sites': sites,
                'inserted_IFn_numbers': inserted,
                'verified_inverse_numbering': renamed,
                'complete_function_reconstructed_exactly': True,
            })
        return current

    restored = FUNCTION.sub(restore_function, new)
    assert restored == prior, (name, 'complete IR reconstruction differs')
    return path_changes, bounds, ascii_changes


results = []
mapping = []
counts = Counter()
raw_message_changes = 0
oracle_normalized_messages = 0
oracle_diagnostic_changes = 0
status_changes = []
ir_presence_changes = []
reported_names = []

for index, name in enumerate(cases, 1):
    directory = EVIDENCE / str(index)
    report_file = directory / 'report'
    assert report_file.is_file(), (index, name)
    report = report_file.read_text()
    old_msg = (directory / 'old.msg').read_text()
    new_msg = (directory / 'new.msg').read_text()
    status = re.findall(r'^  exit status (.+)$', report, re.M)
    presence = re.findall(r'^  IR written by only one compiler$', report, re.M)
    if status:
        status_changes.append({'case': name, 'change': status})
    if presence:
        ir_presence_changes.append(name)
    assert '  no result (its worker died)' not in report
    assert '  cannot normalize diagnostics' not in report
    mapping.append({'index': index, 'case': name, 'differs': bool(report), 'report_sha256': sha(report.encode())})
    if old_msg != new_msg:
        raw_message_changes += 1
        assert (directory / 'old.normal.msg').is_file()
        assert (directory / 'new.normal.msg').is_file()
        if (directory / 'old.normal.msg').read_bytes() == (directory / 'new.normal.msg').read_bytes():
            oracle_normalized_messages += 1
            assert '  messages:' not in report
    if not report:
        continue
    reported_names.append(name)
    record = {
        'index': index, 'case': name, 'evidence_directory': str(directory),
        'report_sha256': sha(report.encode()),
        'old_diagnostic_sha256': sha(old_msg.encode()),
        'new_diagnostic_sha256': sha(new_msg.encode()),
        'status_equal_in_original_oracle': not status,
    }
    if '  messages:' in report:
        oracle_diagnostic_changes += 1
        record['diagnostic_locations'] = explain_diagnostic(old_msg, new_msg)
        record['old_diagnostic'] = old_msg
        record['new_diagnostic'] = new_msg
        assert not (directory / 'old.ll').exists() and not (directory / 'new.ll').exists()
        record['category'] = 'path_only_diagnostics'
        record['complete_diagnostic_reconstructed_exactly'] = True
    else:
        assert (directory / 'old.ll').is_file() and (directory / 'new.ll').is_file()
        old_ir = (directory / 'old.ll').read_text()
        new_ir = (directory / 'new.ll').read_text()
        record['old_ir_sha256'] = sha(old_ir.encode())
        record['new_ir_sha256'] = sha(new_ir.encode())
        paths, bounds, ascii_changes = explain_ir(name, old_ir, new_ir)
        record['path_changes'] = paths
        record['bounds_changes'] = bounds
        record['ascii_changes'] = ascii_changes
        record['complete_ir_reconstructed_exactly'] = True
        if paths and not bounds and not ascii_changes:
            category = 'path_only_ir'
        elif bounds and not paths and not ascii_changes:
            category = 'bounds_only'
        elif ascii_changes and not paths and not bounds:
            category = 'ascii_only'
        elif paths and bounds and not ascii_changes:
            category = 'path_and_bounds'
        elif paths and ascii_changes and not bounds:
            category = 'path_and_ascii'
        else:
            raise AssertionError((name, 'unexpected category overlap'))
        record['category'] = category
    counts[record['category']] += 1
    results.append(record)

assert reported_names == log_changed
assert len(results) == 272
assert not status_changes and not ir_presence_changes
assert seen_ascii == set(ASCII_SITES)
assert oracle_diagnostic_changes == 13
assert raw_message_changes == oracle_normalized_messages + oracle_diagnostic_changes
assert counts == {
    'path_only_ir': 246, 'path_only_diagnostics': 13,
    'bounds_only': 8, 'ascii_only': 3, 'path_and_bounds': 1, 'path_and_ascii': 1,
}
bounds_cases = [r for r in results if r.get('bounds_changes')]
ascii_cases = [r for r in results if r.get('ascii_changes')]
paths_ir = [r for r in results if r.get('path_changes')]
candidate_checkout = git(NEW, 'rev-parse', 'HEAD')
later_changes = git(NEW, 'diff', '--name-only', INITIAL_CANDIDATE, candidate_checkout).splitlines()
assert set(later_changes) <= {'bench/runtime_subset/compare.py', 'bench/runtime_subset/workload.py'}
library_proof = {
    'old_commit': git(OLD, 'rev-parse', 'HEAD'), 'new_commit': git(NEW, 'rev-parse', 'HEAD'),
    'old_lib_git_tree': old_tree, 'new_lib_git_tree': new_tree,
    'all_90_common_files_equal_in_bytes_and_modes': True,
    'python_source_files': 87,
    'common_file_manifest': old_lib,
    'candidate_only_files': {n: new_lib[n] for n in extras},
    'candidate_only_files_consumed_by_native_loader': False,
    'loader_evidence': 'loader.py:1015-1077 resolves standins to .py and searches only name.py or name/__init__.py; CPython .pyc is not an input',
    'complete_disk_trees_identical': False,
}
summary = {
    'description': 'Every original-oracle difference classified by exact reconstruction of complete retained outputs',
    'baseline_root': str(OLD), 'candidate_root': str(NEW),
    'baseline_checkout_commit': library_proof['old_commit'],
    'candidate_checkout_commit_at_review_start': INITIAL_CANDIDATE,
    'candidate_checkout_commit_at_classification': candidate_checkout,
    'candidate_later_changed_files_outside_oracle_inputs': later_changes,
    'compiler_runtime_library_and_corpus_sources_unchanged_during_analysis': True,
    'baseline_native_compiler_sha256': sha((OLD / 'pystachy').read_bytes()),
    'candidate_native_compiler_sha256': sha((NEW / 'pystachy').read_bytes()),
    'original_log': str(LOG), 'original_log_sha256': sha(LOG.read_bytes()),
    'reporting_script': str(BASE / 'irsame-evidence.sh'),
    'reporting_script_sha256': sha((BASE / 'irsame-evidence.sh').read_bytes()),
    'analysis_script': str(Path(__file__)), 'analysis_script_sha256': sha(Path(__file__).read_bytes()),
    'evidence_directory': str(EVIDENCE), 'case_map': str(CASE_MAP),
    'corpus_cases': len(cases), 'oracle_identical_cases': len(cases) - len(results),
    'oracle_differing_cases': len(results),
    'difference_counts': dict(sorted(counts.items())),
    'unexplained_cases': 0,
    'status_difference_count': 0, 'one_sided_ir_count': 0, 'missing_reports': 0,
    'status_evidence_limit': 'The original harness compared both exit codes for every case; it retained differences, not individual equal numeric exit codes',
    'diagnostic_audit': {
        'raw_message_pairs_differing_before_oracle_location_normalization': raw_message_changes,
        'safely_normalized_by_original_oracle': oracle_normalized_messages,
        'remaining_oracle_diagnostic_differences': oracle_diagnostic_changes,
        'remaining_explained_by_specific_location_prefixes': oracle_diagnostic_changes,
        'non_location_diagnostic_changes': 0, 'new_rejections': 0,
    },
    'bounds': {
        'case_count': len(bounds_cases),
        'getter_replacements': sum(len(r['bounds_changes']) for r in bounds_cases),
        'cases': [r['case'] for r in bounds_cases],
    },
    'ascii': {
        'case_count': len(ascii_cases),
        'function_count': sum(len(r['ascii_changes']) for r in ascii_cases),
        'new_protected_calls': sum(len(a['sites']) for r in ascii_cases for a in r['ascii_changes']),
        'cases': [r['case'] for r in ascii_cases],
        'all_other_block_value_changes_exactly_match_IFn_number_insertions': True,
    },
    'checkout_path_ir': {
        'case_count_including_overlaps': len(paths_ir),
        'generated_import_error_globals': sum(p['kind'] == 'generated_import_error_location' for r in paths_ir for p in r['path_changes']),
        'installation_prefix_globals': sum(p['kind'] == 'compiler_installation_prefix' for r in paths_ir for p in r['path_changes']),
    },
    'library_identity': library_proof,
    'method': [
        'Reconstructed the exact shell corpus order and matched all 4245 report directories and all 272 DIFF names in order.',
        'Checked every report for status mismatches, one-sided IR, missing results and diagnostic normalization errors.',
        'Verified the shared Git lib tree, all common files by SHA-256 and mode, and all 87 Python sources; recorded the sole extra CPython cache.',
        'Reconciled only generated ImportError source-location substrings and two individually reviewed sys.prefix string constants.',
        'Reversed a new four-instruction load only when its result, list and index exactly matched the old function\'s getter call.',
        'Reviewed all six ASCII unwind targets against the source try and old landing pad/invokes; reversed only those six call-to-invoke changes.',
        'Removed only the verified ASCII continuation labels with no other incoming references; reversed exactly their IFn.n offsets in local SSA values and block labels.',
        'Required whole-file byte equality after these changes for all 259 differing IR pairs, and exact diagnostic equality after location-only changes for the remaining 13.',
    ],
    'limits': [
        'The raw oracle remains intentionally nonidentical: 272 of 4245 differ. This classification is not a claim that an unmodified irsame run passed.',
        'Checkout commits are observations of source state during review; the retained output hashes and compiler hashes identify this evidence, while bootstrap source provenance is maintained by the parent verification run.',
        'This is a static comparison of retained outputs, not native correctness, performance or memory evidence.',
        'Checkout path differences remain recorded; no shared compiler home or broad text normalization was used.',
        'The log includes two reporting-pipeline sed broken-pipe warnings; all per-case reports are complete, and full retained output comparisons were used here.',
    ],
    'cases': results,
}
CASE_MAP.write_text(json.dumps(mapping, indent=2) + '\n')
REPORT.write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({
    'report': str(REPORT), 'corpus': len(cases), 'different': len(results),
    'counts': dict(sorted(counts.items())), 'unexplained': 0,
    'diagnostics': summary['diagnostic_audit'], 'bounds': summary['bounds'],
    'ascii': summary['ascii'], 'checkout_path_ir': summary['checkout_path_ir'],
}, indent=2))
