#!/usr/bin/env python3
"""Publishable index of immutable startup, inspection, and fnmatch follow-up evidence."""
from pathlib import Path
import json
from inspect_series import digest

ROOT = Path(__file__).resolve().parent


def item(path, role='authoritative evidence'):
    path = Path(path).resolve()
    return {'path': str(path), 'relative_path': str(path.relative_to(ROOT)),
            'bytes': path.stat().st_size, 'sha256': digest(path), 'role': role}


def write_new(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


def main():
    earlier_path = ROOT / 'curated-ea685-startup.json'
    startup_path = ROOT / 'results-ea685/report.json'
    long_path = ROOT / 'fnmatch-ea685-long/report.json'
    link_path = ROOT / 'inspection-ea685-backend-link-v2.json'
    earlier, startup, followup, linkage = [json.loads(path.read_text()) for path in (earlier_path, startup_path, long_path, link_path)]
    assert startup['status'] == followup['status'] == linkage['status'] == 'complete'
    assert len(startup['samples']) == 108 and len(followup['samples']) == 36
    assert followup['startup_report_sha256'] == digest(startup_path) == earlier['reports']['startup']['sha256']
    for path, value in followup['inputs'].items():
        assert digest(path) == value, path
    for row in followup['samples']:
        assert row['returncode'] == 0 and row['stdout'] == followup['oracles'][str(row['iterations'])]['stdout']
    assert linkage['augmentation']['exact_match']
    assert digest(link_path) == earlier['reports']['linkage']['sha256']
    result = dict(earlier)
    result['schema'] = 2
    result['status'] = 'complete evidence; performance acceptance remains open'
    result['evidence_completion'] = {'startup_samples': 108, 'duration_followup_samples': 36,
        'hosted_inspection_cells': 6, 'all_checksums_passed': True, 'all_identity_checks_passed': True,
        'exact_driver_augmentation': True, 'authoritative_symbol_join': 'quoted-name-aware v2',
        'performance_acceptance_established': False}
    result['duration_followup'] = followup
    result['methods']['duration_followup'] = item(ROOT / 'fnmatch_followup.py', 'executed follow-up method')
    result['reports']['duration_followup'] = item(long_path)
    result['history'] = {'earlier_curated_checkpoint': item(earlier_path, 'completed startup checkpoint, before duration follow-up'),
        'inspection_summary_snapshot': item(ROOT / 'inspection-ea685-summary.json', 'hosted snapshot before native linkage; pending label is historical'),
        'first_linkage': item(ROOT / 'inspection-ea685-backend-link.json', 'exact augmentation valid; printed-spelling symbol join superseded by v2'),
        'authoritative_linkage': item(link_path, 'exact augmentation and corrected quoted-name-aware structural join')}
    result['inspection_summary'] = {'historical_hosted_snapshot': earlier['inspection_summary'],
        'current_linkage_status': 'complete', 'authoritative_linkage': item(link_path),
        'note': 'The embedded snapshot was frozen before linkage and intentionally retains its historical pending label.'}
    result['fnmatch_aot_investigation']['interpretation'] = (
        'The n=1000 local final/main loops are slower in all six pairs. Longer runs retain positive median costs: '
        'n=10000 +5.25% by loop medians/+3.72% paired median; n=100000 +8.34%/+8.86%, four slower pairs of six at both sizes. '
        'At n=100000 CPU is also +8.95% by medians/+9.42% paired median. Thus the follow-up does not clear the concern. '
        'CI reports +1.21% at n=1000 on another CPU with three samples. Retain both hosts and all vectors separately; no threshold is inferred.')
    result['fnmatch_aot_investigation']['followup_data_key'] = 'duration_followup'
    result['final_findings'] = {'whole_opt_plus_lli_vs_current_main_percent': 9.554282804505831,
        'whole_opt_plus_lli_vs_historical_da84_percent': -6.071292445977605,
        'jit_process_median_overhead_percent': {case:100*(data['jit_wall_s']['final_comparisons']['main']['median_ratio']-1) for case,data in startup['summary'].items()},
        'jit_process_paired_median_overhead_percent': {case:100*(data['jit_wall_s']['final_comparisons']['main']['paired_median']-1) for case,data in startup['summary'].items()},
        'conclusion': 'Startup improved over the handoff source, but current-main whole-process/tool work and longer fnmatch AOT costs remain. This evidence does not establish performance acceptance.'}
    result['limitations'] = [line for line in result['limitations'] if 'prepared but unexecuted' not in line]
    result['limitations'].append('The two elapsed series are distinct experiments and are not pooled; the original108 observations and both earlier linkage records remain unchanged.')
    final_path = ROOT / 'curated-ea685-final.json'
    write_new(final_path, result)
    files = [startup_path, long_path, ROOT / 'inspection-ea685/report.json', link_path,
             ROOT / 'measure_current_v2.py', ROOT / 'backend_tool_wrapper.py', ROOT / 'inspect_series.py',
             ROOT / 'link_inspection_backend_v2.py', ROOT / 'fnmatch_followup.py',
             ROOT / 'reproduce-ea685.txt', ROOT / 'ea685-final-readme.txt',
             ROOT / 'inspection-ea685-backend-link-v2-artifacts/target-prefix.ll',
             ROOT / 'inspection-ea685-backend-link-v2-artifacts/object-hooks.ll', Path(__file__), final_path]
    selected = [item(path) for path in files]
    selected.extend([item(ROOT / 'inspection-ea685-summary.json', 'historical pre-linkage hosted summary'),
                     item(ROOT / 'inspection-ea685-backend-link.json', 'superseded printed-symbol join; valid exact augmentation'),
                     item(earlier_path, 'historical startup checkpoint before duration follow-up')])
    manifest = {'schema': 2, 'status': 'final curated selection', 'destination_prefix': 'startup-ea685/',
                'layout': 'Preserve each relative_path beneath destination_prefix so helper imports and report subdirectories remain intact.',
                'files': selected, 'total_bytes': sum(row['bytes'] for row in selected),
                'raw_archive_policy': 'All raw profiles/captures, compiled executables and complete expected augmented module remain locally retained with hashes and paths in the curated archive inventory.'}
    index = ROOT / 'publication-ea685-final.json'
    write_new(index, manifest)
    print(json.dumps({'curated': item(final_path), 'index': item(index), 'files': len(selected), 'publication_bytes': manifest['total_bytes']}))


if __name__ == '__main__':
    main()
