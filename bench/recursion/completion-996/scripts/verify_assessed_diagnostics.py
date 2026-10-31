#!/usr/bin/env python3
"""Replay the published diagnostic proof using recorded byte spans, not regexes.

This independently verifies the byte-substitution relation in the self-contained
assessment.  The producing controller separately verifies source bytes against
the original manifests and actual pinned Git blobs.
"""

import argparse
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(assessment):
    assert assessment['original_comparison']['gate_passed'] is False
    assert assessment['original_comparison']['status'] == 'failed'
    assert len(assessment['cases']) == 29
    assert len(assessment['source_files']) == 10
    token_count = 0
    for case in assessment['cases']:
        residuals = {}
        for role in ('main', 'candidate'):
            streams = case['streams'][role]
            for record in streams.values():
                data = record['text'].encode('utf-8')
                assert sha(data) == record['sha256'] and len(data) == record['bytes']
            assert streams['stdout']['text'] == ''
            stderr = streams['stderr']['text'].encode('utf-8')
            prefix = assessment['library_homes'][role].encode('utf-8') + b'/'
            chunks, offset = [], 0
            for token in case['path_tokens']:
                start, stop = token[role + '_byte_span']
                assert offset <= start < stop <= len(stderr)
                raw = token[role + '_raw_token'].encode('utf-8')
                relative = token['relative_source'].encode('utf-8')
                line = str(token['line']).encode('ascii')
                assert stderr[start:stop] == raw == prefix + relative + b':' + line
                source = assessment['source_files'][token['relative_source']]
                assert token['source_sha256'] == source['source_sha256']
                assert source['roles']['main']['sha256'] == source['roles']['candidate']['sha256'] == token['source_sha256']
                assert source['roles']['main']['git_blob'] == source['roles']['candidate']['git_blob']
                chunks.extend([stderr[offset:start], b'<OWN_LIBRARY>/', relative, b':', line])
                offset = stop
            chunks.append(stderr[offset:])
            assert stderr.count(prefix) == len(case['path_tokens'])
            residuals[role] = b''.join(chunks)
        assert residuals['main'] == residuals['candidate'] == case['normalized_stderr'].encode('utf-8')
        assert sha(residuals['main']) == case['normalized_stderr_sha256']
        token_count += len(case['path_tokens'])
    assert token_count == 74
    return {'cases': 29, 'path_tokens_per_role': 74, 'source_files': 10,
            'byte_span_replay_passed': True, 'original_failed_gate_preserved': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assessment', required=True, type=Path)
    args = parser.parse_args()
    data = args.assessment.read_bytes()
    result = verify(json.loads(data))
    result['assessment_sha256'] = sha(data)
    result['verifier_sha256'] = sha(Path(__file__).read_bytes())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
