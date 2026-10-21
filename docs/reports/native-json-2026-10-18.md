# Native JSON prototype checkpoint — 2026-10-18

This experiment enables recursive native JSON and measures a real record consumer.
It does not implement runtime profiling or automatic specialization. Refs #9,
#257 and #392; none of their wider acceptance scopes is claimed complete.

The source was frozen at local commit
`31807d276494da85d9a1a5d085a0554ee637da0e`, clean tree
`4f2814949797e0426127af22f3f6d64865c3996a`, based on main
`a355c83ff7b60b64e3264867593064c3da9611a5`. The publication adds this report and
raw evidence without changing the measured implementation. Source/input hashes
and every sample are in [the JSON report](native-json-2026-10-18.json).

## Measurement

```sh
python3.13 tools/bench_json.py --compiler ./pystachy \
  --records 5000 --iterations 10 --samples 3 --processes 3 \
  --json build/json-benchmark-final.json
```

CPython 3.13.16; LLVM 18.1.3; Linux x86-64 shared host with 9 available CPUs;
starting load averages 3.30, 3.39, 2.93. No owned builds or broad tests ran alongside
the measurements. Each profile has 5,000 nested UTF-8 records (496–506 kB).
Each configuration ran in three fresh processes, with three samples of ten
iterations per process. The table uses the median of process medians, in
milliseconds per document. All 54 process/configuration runs matched CPython's
full checksums; three separate AOT GC probes also matched.

| Profile | CPython generic parse | JIT generic parse | AOT generic parse | CPython generic process | JIT generic process | AOT generic process | AOT guarded process |
|---|---:|---:|---:|---:|---:|---:|---:|
| Skewed (92% integer amounts) | 12.027 | 33.329 | 33.573 | 5.725 | 0.919 | 0.727 | 0.598 |
| Mixed (no integer amounts) | 7.451 | 34.900 | 40.604 | 4.025 | 0.953 | 0.991 | 0.872 |
| Changing (phase shift halfway) | 7.697 | 31.582 | 30.738 | 3.725 | 0.687 | 0.680 | 0.708 |

Generic AOT parse-plus-process medians were 32.265, 40.916 and 28.369 ms;
CPython's were 18.138, 11.405 and 11.590 ms. These phases are measured separately,
so their samples need not add to the table's independently timed phases.
Native processing is promising, but parsing dominates the end-to-end workload
and is slower than CPython's C decoder in this experiment.

The guarded path is source-written and retains a generic fallback. Its processing
ranges overlap the generic ranges in all three AOT profiles: skewed generic
0.705–0.793 versus guarded 0.577–0.788 ms; mixed 0.829–1.203 versus
0.690–1.376; changing 0.642–0.695 versus 0.685–0.714. Even the mixed profile,
which cannot take the integer fast path, shows a lower guarded median. Parse
timings also vary across algorithm labels although parsing is identical. These
are noisy exploratory results, not evidence for a reliable specialization gain.

AOT build time was 1.869 s and executable size 124,560 bytes. Full process wall
times, including JIT compilation where applicable, remain separate in the raw
report. The initial runtime-cache probe took 0.086 s; this is not a measured cold
cache build. Separate AOT probes reported 25 collections, 185–190 ms collecting
and 51.1–52.2 MiB peak managed heap across the full repeated workload. GNU time
was unavailable, so peak RSS is unmeasured; GC statistics are not allocation
counts. The experiment does not measure serialization throughput.

Next useful experiments are faster string/token scanning and fewer transient
allocations, followed by controlled processing-only profiles on an idle host.
Automatic guarded cloning would need its own type profiles, fallback tests,
version budget and compile/startup accounting. No online compiler is justified
by this measurement alone.

## Local validation

- Full bootstrap passed: compiler stage1/2/3 IR identical (624,400 lines), runtime
  stage1/2/3 IR identical (18,388 lines). Native compiler SHA-256:
  `2e586793362c65c6a2d83e37c02a60668e52035891b61eac19cdb6b97e8fca2b`.
- Full IR corpus: 1,377 programs accepted by the internal checker and LLVM.
  All 25 IR contract probes pass. Three object-key effect snapshots intentionally
  gained conservative effects from recursive comparison guards; see the design doc.
- Runtime contract checker: 446 entries, 70 exception classes agree, with no
  forbidden runtime-lowering recursion among 170 subset-runtime functions.
- Focused native JIT/AOT, collecting at every program allocation: 45 selected
  JSON/recursive-alias/union/Any/type-alias cases, 85 passes. The final cyclic
  comparison fixture is checked separately. Compiler alias checks also passed
  with optimizations disabled and collection at every program allocation.
- `tools/json_check.py --compiler ./pystachy --native --gc-stress`: 19,022 hosted
  differential/limit checks and 11,017 cases in each of JIT and AOT passed.
- `make eqprobe` passed normally and with collection at every allocation,
  including recursive descriptor equality, nested mutation and cycle representation.
- Benchmark harness: three evidence-validation tests passed; no-argument consumer
  prints the same checksum on pinned CPython, JIT and AOT.

Initial checks exposed missing development-only `typing_extensions` in the pinned
interpreter, resolved in an isolated environment using version 4.16.0. A depth
fixture was moved into explicit deviation coverage because CPython 3.13 accepts
deeper values than the prototype's fixed runtime budget. Intermediate recording
checks overlapped that move and were rerun after the source settled. These were
setup/fixture corrections, not passing final checks.

The complete `make verify` matrix, full UBSan/GC corpus, package/port acceptance
and existing-workload performance remain unrun locally. This is a draft
prototype requiring maintainer design review and applicable CI before merge.
