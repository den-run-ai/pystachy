"""Curate a completed kernel series without executing or relabeling observations."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--harness', type=Path, required=True)
    parser.add_argument('--publish', type=Path, required=True)
    args = parser.parse_args()
    base, harness, publish = args.input.resolve(), args.harness.resolve(), args.publish.resolve()
    raw = base / 'measurement.json'
    data = json.loads(raw.read_text())
    assert data['status'] == 'complete'
    assert all(data['phases'][phase]['status'] == 'passed' for phase in ('prepare', 'counts', 'timings'))
    assert data['source_identities']['main']['commit'] == '07b26e02425d023288ed95a9d2a5077be5aeb45e'
    assert data['source_identities']['final']['commit'] == 'ea68529b8a590eb8f3df7200b857e1d16becd7a3'
    assert len(data['cases']) == 7
    orders = data['timing_orders']
    assert len(orders) == 6 and len({tuple(order) for order in orders}) == 6
    for phase in data['phases'].values():
        assert phase['harness_sha256'] == data['phases']['prepare']['harness_sha256']
    for name, expected in data['phases']['prepare']['harness_sha256'].items():
        assert digest(harness / name) == expected
    summary = {
        'status': 'complete', 'raw_measurement_sha256': digest(raw),
        'comparison': 'Fresh current main 07b26e0 and final ea685; archived da84 is an explicitly historical source reference. All observations in this series are new.',
        'sources': {name: {'commit': row['commit'], 'tree': row['tree']} for name, row in data['source_identities'].items()},
        'build_provenance': data['native_compilers'], 'timing_orders': orders,
        'timing_statistic': 'Each process contributes the median of seven in-process kernel durations. Paired ratios compare process medians within the same round; range means observed minimum/maximum, not a confidence interval.',
        'count_scope': 'Eight complete kernel calls including warmup and runtime/GC; compilation, printing and timer calls excluded. Client marker boundaries are distinguished from unmodified AOT f.kernel entry/return. Raw non-entry function bodies match under instrumentation; downstream JIT machine-code equality is not claimed.',
        'uncertainty': 'Short process medians are approximately 7–21 ms and paired ratios vary widely. Longer cases also contain substantial variation. Retain all observations; do not interpret isolated signed timing percentages as precise speedups or regressions, pool workloads, or treat ranges as confidence intervals.',
        'cases': {}, 'observations': {'timing_processes': 0, 'instruction_counts': 0},
    }
    timing_lines = ['| Case | Mode | n | Main loop ms | da84 loop ms | Final loop ms | Paired final/main | Observed paired range | Slower pairs |',
                    '|---|---|---:|---:|---:|---:|---:|---|---:|']
    count_lines = ['| Case | Mode | Count n | Main instructions | da84 instructions | Final instructions | Final/main | Final/da84 |',
                   '|---|---|---:|---:|---:|---:|---:|---:|']
    for case, source in data['cases'].items():
        result = {'timing_n': source['n'], 'extra_untimed_calls': source['extra_untimed_kernel_calls'],
                  'checksum': source['checksum'], 'source_sha256': source['source_sha256'],
                  'timings': {}, 'per_mode_provenance': {}}
        summary['cases'][case] = result
        for mode in ('jit', 'aot'):
            runs = source['timings'][mode]
            medians = {}
            for role, rows in runs.items():
                assert len(rows) == 6
                for index, row in enumerate(rows):
                    assert row['round'] == index and row['order'] == orders[index]
                    assert row['returncode'] == 0 and row['checksum'] == source['checksum']
                    assert len(row['sample_ns']) == 7 and min(row['sample_ns']) > 0
                medians[role] = [row['median_ns'] for row in rows]
                summary['observations']['timing_processes'] += len(rows)
            stats = {}
            for role, values in medians.items():
                pairs = [value / baseline for value, baseline in zip(values, medians['main'], strict=True)]
                stats[role] = {'process_medians_ns': values, 'median_loop_ns': statistics.median(values),
                    'median_loop_ms': statistics.median(values) / 1e6, 'process_range_ns': [min(values), max(values)],
                    'paired_ratios_to_main': pairs, 'paired_ratio_median_to_main': statistics.median(pairs),
                    'paired_percent_to_main': 100 * (statistics.median(pairs) - 1),
                    'paired_ratio_range_to_main': [min(pairs), max(pairs)], 'slower_pairs_to_main': sum(value > 1 for value in pairs),
                    'ratio_of_process_medians_to_main': statistics.median(values) / statistics.median(medians['main'])}
            paired_da84 = [value / baseline for value, baseline in zip(medians['final'], medians['da84'], strict=True)]
            result['timings'][mode] = {'variants': stats, 'final_paired_ratios_to_da84': paired_da84,
                'final_paired_median_to_da84': statistics.median(paired_da84), 'final_paired_range_to_da84': [min(paired_da84), max(paired_da84)]}
            result['per_mode_provenance'][mode] = {role: {
                'command_example': runs[role][0]['command'], 'cwd': runs[role][0]['cwd'],
                'native_compiler_sha256': data['native_compilers'][role]['sha256'],
                'raw_ir_sha256': source['frontend_ir'][role]['sha256'],
                'hosted_ir_sha256': source['frontend_ir'][role]['hosted_ir_sha256'],
                'aot_executable_sha256': source['builds'][role]['sha256'] if mode == 'aot' else None,
            } for role in runs}
            f = stats['final']; bounds = f['paired_ratio_range_to_main']
            timing_lines.append(f"| {case} | {mode.upper()} | {source['n']:,} | {stats['main']['median_loop_ms']:.4f} | {stats['da84']['median_loop_ms']:.4f} | {f['median_loop_ms']:.4f} | {f['paired_percent_to_main']:+.2f}% | {100*(bounds[0]-1):+.2f}% to {100*(bounds[1]-1):+.2f}% | {f['slower_pairs_to_main']}/6 |")
        if 'instruction_counts' in source:
            counted = source['instruction_counts']
            result['instruction_counts'] = {'n': counted['n'], 'checksum': counted['checksum'], 'kernel_calls': 8, 'modes': {}}
            for mode in ('jit', 'aot'):
                rows = {role: pair[mode] for role, pair in counted['variants'].items()}
                for row in rows.values():
                    assert row['returncode'] == 0 and row['checksum'] == counted['checksum']
                    assert row['all_non_entry_function_bodies_identical']
                    assert row['collection'] == 'client markers' or row['verified_kernel_returns'] == 8
                values = {role: row['instructions'] for role, row in rows.items()}
                result['instruction_counts']['modes'][mode] = {
                    'instructions': values, 'final_percent_vs_main': 100 * (values['final'] / values['main'] - 1),
                    'final_percent_vs_da84': 100 * (values['final'] / values['da84'] - 1),
                    'collection': {role: row['collection'] for role, row in rows.items()},
                    'profile_sha256': {role: row['profile_sha256'] for role, row in rows.items()},
                }
                summary['observations']['instruction_counts'] += len(rows)
                count_lines.append(f"| {case} | {mode.upper()} | {counted['n']:,} | {values['main']:,} | {values['da84']:,} | {values['final']:,} | {100*(values['final']/values['main']-1):+.4f}% | {100*(values['final']/values['da84']-1):+.4f}% |")
    assert summary['observations'] == {'timing_processes': 252, 'instruction_counts': 24}
    analysis = base / 'analysis.json'
    analysis.write_text(json.dumps(summary, indent=2) + '\n')
    publish.mkdir(parents=True, exist_ok=False)
    for filename in ('measurement.json', 'curated.json', 'analysis.json'):
        shutil.copyfile(base / filename, publish / filename)
    for filename in data['phases']['prepare']['harness_sha256']:
        shutil.copyfile(harness / filename, publish / filename)
    shutil.copyfile(Path(__file__), publish / Path(__file__).name)
    shutil.copytree(base / 'probes', publish / 'probes')
    for filename in ('prepare-ea685.log', 'counts-ea685.log'):
        shutil.copyfile(harness / filename, publish / filename)
    readme = '''# Current-main kernel evidence for PR #996

This completed series contains all **252 timing processes** and **24 instruction-count observations**. Current main is `07b26e02425d023288ed95a9d2a5077be5aeb45e`; final is `ea68529b8a590eb8f3df7200b857e1d16becd7a3`. The archived `da84d382ff83f09e46d4ef104e62e6f64e9c37c1` source is a historical comparison, separately identified throughout. Both current-main and final native compilers have fresh certified fixed points. The closed db14/06e3 checkpoint was not pooled or relabeled.

`measurement.json` contains every original command, stdout/stderr, checksum, sample, round/order, source/tool/build binding and count-collection detail. `analysis.json` adds absolute loop durations, within-round paired ratios/ranges and per-mode provenance. `curated.json` is the frozen measurement harness's own summary. No observations were removed.

## Instruction counts

Each observation covers eight complete kernel calls, including warmup and runtime/GC. Compilation, timers and printing are outside collection. Count input sizes differ from timing sizes and are explicit below. JIT uses client markers. AOT uses the unmodified `f.kernel` symbol where retained; ordinary-call AOT uses the documented marker fallback in all three variants. All original non-entry raw function bodies were verified identical under instrumentation; this does not assert identical downstream JIT machine code.

''' + '\n'.join(count_lines) + '''

Ordinary/object final counts exactly match da84 in both modes; current-main differences are tiny fixed entry costs at these input sizes. JSON retains measurable overhead versus current main, reduced relative to da84. These are complete kernel observations, not compiler-startup counts.

## Elapsed kernel observations

Each process warms the kernel, then records seven calls; its contribution is their median. Six balanced variant orders provide six within-round final/main ratios. The displayed absolute time is the median of the six process medians. Ranges are observed min/max ratios, **not confidence intervals**. Warmed JSON has four additional untimed kernel calls. All timing phases ran in an explicitly coordinated quiet window with other task agents paused.

''' + '\n'.join(timing_lines) + '''

Short loops last roughly 7–21 ms, and many paired ranges cross zero widely. Longer object and AOT cases also vary substantially. In particular, the original short JSON JIT ratio of process medians is negative while its within-round median ratio is positive. Neither isolated statistic establishes a precise general speedup. The longer JSON JIT observations are consistent with a few-percent cost; AOT timing estimates remain less stable than the instruction counts. Retain the full distribution when reviewing acceptance; no outlier filtering, workload pooling, or significance claim is applied.

## Reproduction and artifact scope

Keep `measure_current.py`, `count_support.py` and `replay_support.py` together. Their exact hashes are in the raw phase records. The scripts use the recorded recovery workspace/toolchain paths and expect the original `final-perf/` placement; restore that layout from the archive before rerunning. This publication directory is a review selection, not a relocated execution environment. Run the three phases sequentially in a new output directory with the final commit argument and certified fresh bootstrap record. The original command records, environment allowlist, private cache locations, CPU pin and tool hashes are in `measurement.json`.

The source probes are included under `probes/`. All generated LLVM, binaries, Callgrind files, caches and count-attempt JSON remain in the complete `final-perf/results-ea685` archive; their hashes and original paths remain in the report. This selection retains the complete raw observation report and companion scripts while leaving those larger artifacts in the archive. `curate_current.py` is the separate read-only derivation/publication controller; it does not run a compiler or benchmark.
'''
    (publish / 'README.md').write_text(readme)
    manifest = {str(path.relative_to(publish)): {'sha256': digest(path), 'bytes': path.stat().st_size}
                for path in sorted(publish.rglob('*')) if path.is_file()}
    (publish / 'manifest.json').write_text(json.dumps({'files': manifest, 'observations': summary['observations']}, indent=2) + '\n')
    frozen = base / 'frozen-harness'
    frozen.mkdir(exist_ok=False)
    for filename, expected in data['phases']['prepare']['harness_sha256'].items():
        shutil.copyfile(harness / filename, frozen / filename)
        assert digest(frozen / filename) == expected
    print(json.dumps({'publication': str(publish), 'measurement_sha256': digest(raw),
                      'analysis_sha256': digest(analysis), 'publication_files': len(manifest),
                      'observations': summary['observations']}, indent=2))


if __name__ == '__main__':
    main()
