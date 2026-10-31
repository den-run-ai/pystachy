#!/usr/bin/env python3
"""Assess the retained ea685 diagnostic differences without changing its gate.

This is a source/record audit only.  It never invokes either compiler and never
rewrites the original comparison, case records, streams, or comparison harness.
Every replaced byte belongs to a validated own-checkout source-path prefix.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


REPORT_SHA256 = '425b47eb39da4d4dabfe5ec4c0a8be63d6536bb38e23ee338c88238300b2d2a6'
HARNESS_SHA256 = '2da54d464e5d560e77fc32ce45b659d69b25e82e2b8267c6d8c337ded6887ee7'
COMMITS = {
    'main': '07b26e02425d023288ed95a9d2a5077be5aeb45e',
    'candidate': 'ea68529b8a590eb8f3df7200b857e1d16becd7a3',
}
ROLES = ('main', 'candidate')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(home, *args):
    return subprocess.check_output(['git', '-C', str(home), *args])


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def assess(report_path, output):
    assert not output.exists(), 'Assessment output must be a new directory'
    report_bytes = report_path.read_bytes()
    assert sha(report_bytes) == REPORT_SHA256, 'Unexpected original comparison'
    report = json.loads(report_bytes)
    assert report['status'] == 'failed' and report['gate_passed'] is False
    summary = report['summary']
    assert summary['expected'] == summary['recorded'] == 3924
    assert not summary['missing_cases'] and not summary['validation_failures']
    assert not summary['status_changes']
    assert len(summary['diagnostic_changes']) == 29
    assert len(summary['raw_diagnostic_changes']) == 61
    assert len(summary['proven_checkout_path_normalizations']) == 32
    records = report['records']
    assert len(records) == 3924 and len({row['case'] for row in records}) == 3924
    assert {row['index'] for row in records} == set(range(3924))
    assert {row['case'] for row in records if not row['diagnostics_equal']} == set(summary['diagnostic_changes'])
    assert all(row['status_equal'] and not any(row['validation_errors'].values()) for row in records)

    homes = {role: Path(report['library_homes'][role]) for role in ROLES}
    for role in ROLES:
        assert report['sources'][role]['commit'] == COMMITS[role]
        assert git(homes[role], 'rev-parse', 'HEAD').decode().strip() == COMMITS[role]
        assert git(homes[role], 'rev-parse', 'HEAD^{tree}').decode().strip() == report['sources'][role]['tree']

    frozen_files = {str(report_path): REPORT_SHA256}
    for path, expected in report['evidence_bindings'].items():
        assert sha(Path(path).read_bytes()) == expected, path
        frozen_files[path] = expected
    harness = report_path.parent.parent / 'compare_corpus_current.py'
    assert sha(harness.read_bytes()) == HARNESS_SHA256
    assert report['evidence_bindings'][str(harness)] == HARNESS_SHA256

    source_proofs = {}

    def source_proof(relative):
        if relative in source_proofs:
            return source_proofs[relative]
        assert relative.startswith('lib/') and relative.endswith('.py'), relative
        assert str(Path(relative)) == relative and '..' not in Path(relative).parts
        proof = {'relative_path': relative, 'roles': {}}
        contents = {}
        for role in ROLES:
            path = homes[role] / relative
            assert path.is_file() and not path.is_symlink(), path
            data = path.read_bytes()
            expected = report['input_manifests'][role]['files'][relative]
            assert sha(data) == expected, path
            committed = git(homes[role], 'show', COMMITS[role] + ':' + relative)
            assert committed == data, (role, relative, 'committed blob differs')
            blob = git(homes[role], 'rev-parse', COMMITS[role] + ':' + relative).decode().strip()
            proof['roles'][role] = {
                'path': str(path), 'commit': COMMITS[role], 'git_blob': blob,
                'sha256': expected, 'bytes': len(data),
                'matches_original_input_manifest': True, 'matches_committed_blob': True,
            }
            contents[role] = data
            frozen_files[str(path)] = expected
        assert contents['main'] == contents['candidate'], (relative, 'source contents differ')
        proof['byte_identical_between_roles'] = True
        proof['source_sha256'] = sha(contents['main'])
        proof['line_count'] = len(contents['main'].splitlines())
        source_proofs[relative] = proof
        return proof

    assessments = []
    for row in records:
        if row['case'] not in summary['diagnostic_changes']:
            continue
        assert row['category'] == 'rejection' and row['expected_returncode'] == 1
        assert row['diagnostics_raw_equal'] is False and row['diagnostic_normalization'] is None
        directory = report_path.parent / f"{row['index']:04}"
        case_record = (directory / 'record.json').read_bytes()
        assert json.loads(case_record) == row
        frozen_files[str(directory / 'record.json')] = sha(case_record)
        pair = {'index': row['index'], 'case': row['case'], 'category': row['category'],
                'expected_diagnostic': row['expected_diagnostic'], 'streams': {},
                'original_record_path': str(directory / 'record.json'),
                'original_record_sha256': sha(case_record)}
        normalized, matches, streams = {}, {}, {}
        for role in ROLES:
            result = row['results'][role]
            assert result['outcome'] == 'completed' and result['returncode'] == 1
            streams[role] = {}
            pair['streams'][role] = {}
            for stream in ('stdout', 'stderr'):
                name = result[stream + '_path']
                assert Path(name).name == name
                path = directory / name
                data = path.read_bytes()
                assert sha(data) == result[stream + '_sha256'], path
                frozen_files[str(path)] = sha(data)
                streams[role][stream] = data
                pair['streams'][role][stream] = {
                    'path': str(path), 'sha256': sha(data), 'bytes': len(data),
                    'text': data.decode('utf-8'),
                }
            stderr = streams[role]['stderr']
            prefix = str(homes[role]).encode() + b'/'
            other = 'candidate' if role == 'main' else 'main'
            assert (str(homes[other]).encode() + b'/') not in stderr
            pattern = re.compile(re.escape(prefix) + rb'([A-Za-z0-9_./-]+\.py):([1-9][0-9]*)')
            matches[role] = list(pattern.finditer(stderr))
            assert 2 <= len(matches[role]) <= 4
            assert matches[role][0].start() == 0
            assert stderr.count(prefix) == len(matches[role]), 'Unrecognized own-home path occurrence'
            pieces, offset = [], 0
            for match in matches[role]:
                relative = match[1].decode('ascii')
                line = int(match[2])
                proof = source_proof(relative)
                assert 1 <= line <= proof['line_count'], (relative, line)
                pieces.extend([stderr[offset:match.start()], b'<OWN_LIBRARY>/', match[1], b':', match[2]])
                offset = match.end()
            pieces.append(stderr[offset:])
            normalized[role] = b''.join(pieces)
            assert prefix not in normalized[role]

        assert streams['main']['stdout'] == streams['candidate']['stdout'] == b''
        assert normalized['main'] == normalized['candidate'], 'Residual non-prefix bytes differ'
        assert len(matches['main']) == len(matches['candidate'])
        path_tokens = []
        for a, b in zip(matches['main'], matches['candidate']):
            assert a.group(1, 2) == b.group(1, 2), 'Relative path or line differs'
            relative, line = a[1].decode('ascii'), int(a[2])
            data = (homes['main'] / relative).read_bytes()
            path_tokens.append({
                'relative_source': relative, 'line': line,
                'source_sha256': source_proofs[relative]['source_sha256'],
                'source_line': data.splitlines()[line - 1].decode('utf-8'),
                'main_byte_span': list(a.span()), 'candidate_byte_span': list(b.span()),
                'main_raw_token': a[0].decode('utf-8'), 'candidate_raw_token': b[0].decode('utf-8'),
            })
        leading_pattern = rb'([^\r\n]+\.py):([0-9]+): error: ([^\r\n]*)\n'
        a = re.fullmatch(leading_pattern, streams['main']['stderr'])
        b = re.fullmatch(leading_pattern, streams['candidate']['stderr'])
        assert a is not None and b is not None
        assert a[2] == b[2] and a[3] != b[3]
        pair.update(
            classification='own_checkout_prefix_only_in_leading_and_embedded_source_locations',
            stdout_equal=True, relative_source_paths_and_lines_equal=True,
            all_referenced_full_source_files_byte_identical=True,
            residual_non_prefix_bytes_equal=True,
            strict_gate_refusal='Embedded own-library paths occur inside the message bytes; the frozen leading-location-only normalizer requires those message bytes to be literally equal.',
            path_tokens=path_tokens,
            normalized_stderr=normalized['main'].decode('utf-8'),
            normalized_stderr_sha256=sha(normalized['main']),
        )
        assessments.append(pair)

    assert len(assessments) == 29 and len(source_proofs) == 10
    diff = git(homes['candidate'], 'diff', '--no-ext-diff', '--no-textconv', COMMITS['main'], COMMITS['candidate'], '--', *sorted(source_proofs))
    assert diff == b'', 'Referenced diagnostic-source files changed'
    for path, expected in frozen_files.items():
        assert sha(Path(path).read_bytes()) == expected, ('Audit input drift', path)
    assert report_path.read_bytes() == report_bytes

    assessment = {
        'schema': 1, 'record_kind': 'independent_retained_diagnostic_assessment',
        'status': 'complete',
        'scope': 'The 29 diagnostic differences rejected by the frozen current-main/current-head comparison. No compiler rerun, source edit, original-report edit, IR equivalence claim, or performance acceptance.',
        'original_comparison': {
            'path': str(report_path), 'sha256': REPORT_SHA256,
            'status': 'failed', 'gate_passed': False,
            'expected': 3924, 'recorded': 3924, 'validation_failures': 0, 'status_changes': 0,
            'raw_diagnostic_changes': 61, 'accepted_leading_path_normalizations': 32,
            'strict_diagnostic_changes': 29, 'raw_ir_changes': summary['changed_ir'],
        },
        'original_harness': {'path': str(harness), 'sha256': HARNESS_SHA256},
        'sources': report['sources'], 'library_homes': report['library_homes'],
        'controller': {'path': str(Path(__file__).resolve()), 'sha256': sha(Path(__file__).read_bytes())},
        'summary': {
            'assessed_cases': len(assessments),
            'path_only_cases_with_identical_referenced_source_files': len(assessments),
            'path_tokens_per_role': sum(len(row['path_tokens']) for row in assessments),
            'distinct_source_files': len(source_proofs),
            'source_file_content_changes': 0, 'source_line_number_changes': 0,
            'residual_non_path_byte_changes': 0, 'unassessed_strict_diagnostic_changes': [],
        },
        'conclusion': 'All 29 strict diagnostic differences are exact own-checkout prefix substitutions, including embedded specialization/call-stack locations. Every referenced complete source file is byte-identical and matches its original input manifest and pinned committed blob. The original strict gate remains failed and unchanged; this separate assessment explains its diagnostic differences.',
        'source_files': source_proofs, 'cases': assessments,
        'exact_referenced_source_diff': {'path': str(output / 'diagnostic-source-files.diff'), 'bytes': 0, 'sha256': sha(diff)},
        'frozen_inputs': frozen_files,
    }
    output.mkdir(parents=True)
    (output / 'diagnostic-source-files.diff').write_bytes(diff)
    save(output / 'assessment.json', assessment)
    print(json.dumps(assessment['summary'], indent=2))
    print('assessment_sha256', sha((output / 'assessment.json').read_bytes()))
    return assessment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    assess(args.report.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
