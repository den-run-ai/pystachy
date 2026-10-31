"""Curate the completed, immutable backend attribution records; run no tools."""

from pathlib import Path
import hashlib
import json


ROOT = Path('/workspace/scratch/e858f72517b9/perf-work/backend-attribution-da84')
RAW = ROOT / 'complete.json'
EXPECTED = '5374af1a1bada3138183f33dc513ef55b128de80f802dd61994e16f5301bf352'
data = RAW.read_bytes()
assert hashlib.sha256(data).hexdigest() == EXPECTED
record = json.loads(data)
assert record['status'] == 'complete'
assert all(p['status'] == 'passed' for p in record['phases'].values())


def shape(path):
    contents = path.read_bytes()
    text = contents.decode()
    return {
        'sha256': hashlib.sha256(contents).hexdigest(),
        'bytes': len(contents),
        'lines': text.count('\n'),
        'function_definitions': sum(line.startswith('define ') for line in text.splitlines()),
    }


result = {
    'schema': 'pystachy-recursion-backend-attribution-v1',
    'status': 'complete',
    'performance_acceptance': 'open',
    'raw_record': {'sha256': EXPECTED, 'bytes': len(data), 'filename': 'backend-attribution-da84-full.json'},
    'raw_compressed': {
        'filename': 'backend-attribution-da84-full.json.gz',
        'sha256': hashlib.sha256((ROOT / 'complete.json.gz').read_bytes()).hexdigest(),
        'bytes': (ROOT / 'complete.json.gz').stat().st_size,
        'compression': 'gzip, mtime=0; decompresses to the exact raw_record bytes',
    },
    'purpose': record['purpose'],
    'scope': record['scope'],
    'timing_scope': record['timing_scope'],
    'environment': {
        'host': 'Intel Xeon Platinum 8573C; Linux 6.18.57; separate from historical AMD EPYC 9V74 series',
        'cpu': record['cpu'],
        'toolchain': 'Recovered Python 3.13.16, LLVM 18.1.3, Valgrind 3.22.0; exact manifest hash below',
    },
    'source_identities': record['source_identities'],
    'native_compilers': record['native_compilers'],
    'input_sha256': record['input_sha256'],
    'source': record['source'],
    'arguments': record['arguments'],
    'oracle': record['oracle'],
    'phases': record['phases'],
    'lli_justification': record['lli_justification'],
    'observation_counts': {'normal_captures': 2, 'opt_profiles': 2, 'lli_profiles': 2},
    'module_shapes': {},
    'observations': {},
    'comparisons': {},
    'limitations': [
        'Each stage has one instrumented observation per variant. These are instruction attribution, not elapsed acceptance samples or hardware cycles.',
        'The actual per-variant driver pipelines are retained: main omits always-inline, while final includes it. Same-flags checks compare each profile with its own normal control, not main with final.',
        'All opt inputs are literal matches within each variant. Bitcode is not literally equal because temporary source filenames differ; retained disassembly diffs prove that only ModuleID and source_filename headers change.',
        'Runtime bytes and arguments match each variant\'s normal control and frozen final-measurement cache. Source, native binary, helper and dataset hashes passed pre/post gates.',
        'Whole lli includes JIT compilation, executed benchmark, runtime/GC and teardown. It is not a pure code-generation measurement.',
        'Inclusive function costs overlap, including recursive/cyclic attribution, and must not be summed. Inlined work is attributed to the containing emitted function.',
        'Named LLVM self-cost deltas below exclude anonymous-address names from causal attribution. Complete positive-function records, including anonymous entries, remain in the exact raw record.',
        'Observed wall times include a diagnostic subprocess wrapper and are not a repeated timing series. They justified profiling lli but do not establish a causal elapsed-time decomposition.',
    ],
}
for variant in ('main', 'candidate'):
    folder = ROOT / ('normal-' + variant)
    result['module_shapes'][variant] = {
        'actual_driver_opt_input': shape(folder / 'actual-input.ll'),
        'optimized_disassembly': shape(folder / 'optimized-output.ll'),
        'optimized_bitcode_bytes': (folder / 'optimized-output.bc').stat().st_size,
    }

for name, observation in record['observations'].items():
    curated = {key: value for key, value in observation.items() if key != 'attribution'}
    if 'attribution' in observation:
        attribution = observation['attribution']
        assert sum(f['self_ir'] for f in attribution['all_functions']) == attribution['total_instructions']
        curated['attribution'] = {key: attribution[key] for key in ('total_instructions', 'positive_functions', 'method')}
        curated['attribution']['top_self'] = attribution['top_self'][:20]
        curated['attribution']['top_inclusive'] = attribution['top_inclusive'][:20]
    result['observations'][name] = curated

selected = {
    'opt': ('AlwaysInlinerPass::run', 'parseAssembly(', 'InstCombinePass::run', 'SimplifyCFGPass::run', 'BranchProbabilityInfo::computeEestimateBlockWeight', 'LoopBase<llvm::BasicBlock, llvm::Loop>::getExitBlocks'),
    'lli': ('MachineFunctionPass::runOnFunction', 'SelectionDAGISel::runOnMachineFunction', 'RegAllocBase::allocatePhysRegs', 'SelectionDAG::Combine'),
}
for stage in ('opt', 'lli'):
    left = record['observations'][stage + '_main']['attribution']
    right = record['observations'][stage + '_candidate']['attribution']
    lmap = {f['name']: f for f in left['all_functions']}
    rmap = {f['name']: f for f in right['all_functions']}
    deltas = []
    for name in lmap.keys() | rmap.keys():
        if not name.startswith('llvm::'):
            continue
        a, b = lmap.get(name, {}), rmap.get(name, {})
        deltas.append({
            'name': name,
            'main_self_ir': a.get('self_ir', 0),
            'candidate_self_ir': b.get('self_ir', 0),
            'delta_self_ir': b.get('self_ir', 0) - a.get('self_ir', 0),
            'main_inclusive_ir': a.get('inclusive_ir', 0),
            'candidate_inclusive_ir': b.get('inclusive_ir', 0),
            'delta_inclusive_ir': b.get('inclusive_ir', 0) - a.get('inclusive_ir', 0),
        })
    main, candidate = left['total_instructions'], right['total_instructions']
    result['comparisons'][stage] = {
        'main_ir': main,
        'candidate_ir': candidate,
        'delta_ir': candidate - main,
        'ratio': candidate / main,
        'percent_change': (candidate / main - 1) * 100,
        'largest_positive_named_llvm_self_deltas': sorted(deltas, key=lambda f: (-f['delta_self_ir'], f['name']))[:20],
        'selected_inclusive_rows_do_not_sum': sorted([f for f in deltas if any(pattern in f['name'] for pattern in selected[stage])], key=lambda f: (-f['delta_inclusive_ir'], f['name'])),
    }
main = sum(result['comparisons'][stage]['main_ir'] for stage in ('opt', 'lli'))
candidate = sum(result['comparisons'][stage]['candidate_ir'] for stage in ('opt', 'lli'))
result['comparisons']['combined_stages'] = {
    'main_ir': main, 'candidate_ir': candidate, 'delta_ir': candidate - main,
    'ratio': candidate / main, 'percent_change': (candidate / main - 1) * 100,
    'scope': 'Sum of two disjoint whole-tool processes, not a sum of inclusive function rows; native frontend and driver work are excluded.',
}
result['findings'] = [
    'The remaining mixed-text startup overhead includes demonstrably more LLVM optimization and machine-code generation work.',
    'The final always-inline stage records 318,912,600 inclusive instructions, approximately 61% of the 522,512,746 extra opt instructions; its loop/branch-probability analysis is visible in the profile. This ratio is descriptive attribution and not an ablation estimate of what removing the pass would save.',
    'MachineFunctionPass inclusive instructions rise by 954,423,277. SelectionDAG instruction selection and physical-register allocation also increase, but these nested inclusive rows overlap.',
    'These profiles identify a concrete remaining optimization target. They do not establish that elapsed performance is acceptable, and they do not erase the preserved historical object-JIT regression or the final CI startup comparisons.',
]
output = ROOT / 'curated.json'
output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps({'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'bytes': output.stat().st_size, 'comparisons': {k: {x:y for x,y in v.items() if x in ('main_ir','candidate_ir','delta_ir','ratio','percent_change')} for k,v in result['comparisons'].items()}, 'module_shapes': result['module_shapes']}))
