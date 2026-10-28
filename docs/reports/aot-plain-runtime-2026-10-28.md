# Plain-program AOT runtime pruning, 28 October 2026

[PR #975](https://github.com/den-run-ai/pystachy/pull/975) removes unreachable
promoting-int and dynamic-identity runtime paths from executables whose modules
do not opt in to either feature. On this comparison, all four plain executables
became smaller; spectral and richards builds became faster with separated sample
ranges. No execution regression was confirmed. The opt-in text control grew by
2.2%, and its build and execution timing ranges overlapped.

This is a partial mitigation for [#706](https://github.com/den-run-ai/pystachy/issues/706).
AOT still optimizes the required runtime bitcode with each program. The experiment
does not establish recovery of all build-cost regressions measured against alpha.3
in the [release sweep](release-sweep-2026-10-28.md#performance).

## Inputs and method

| Input | Value |
|---|---|
| Baseline | [5bd492b33cd6bc32fb464d008d543560a8959486](https://github.com/den-run-ai/pystachy/commit/5bd492b33cd6bc32fb464d008d543560a8959486) |
| Candidate | [9b0cedc90c551c821ed6cf39fc6a16433b386212](https://github.com/den-run-ai/pystachy/commit/9b0cedc90c551c821ed6cf39fc6a16433b386212) |
| Tested local commit | `0eee5093c8a0d55b0833f006c6032543dd4752b3`, with the same tree as the published candidate: `3d3f412888e167df912f51f9be56c92cc7b9e01f` |
| Compiler and oracle | CPython-hosted compiler, CPython 3.13.16, LLVM/clang 18.1.3 |
| Host | Linux x86-64, AMD EPYC 9V74, shared host; measurements pinned to logical CPU 0 |
| Sampling | Three interleaved AOT builds and five interleaved JIT/AOT executions per revision and workload; order alternated each pair |
| Runtime caches | Private per revision, warmed before measurement; default compiler, optimizer and GC settings |

Every workload was first run on CPython. Both execution modes were checked against
that exact stdout before timing and on every timed run. Reported build times include
the hosted frontend and AOT backend. JIT process times include the hosted frontend,
JIT compilation, startup and execution; they are not steady-state kernel timings.
AOT process times include executable startup. Loop times below come from the
workloads' own timers.

The source inputs were identical for both revisions. Raw program IR matched byte
for byte for hello, nbody, spectral and richards. The text control differed only in
one `ImportError` diagnostic's checkout path to `lib/types.py` and its string-size
fields; replacing exactly that path and its lengths made the complete IR identical.
This was a five-workload IR comparison, not a full-corpus `make irsame` run.

## Build cost and executable size

Times are median seconds, followed by the full sample range. Sizes are unstripped
executable bytes from the same toolchain, without a relative-size gate.

| Workload | Baseline build | Candidate build | Baseline bytes | Candidate bytes | Interpretation |
|---|---:|---:|---:|---:|---|
| `print(1)` | 0.242 [0.240, 0.244] | 0.251 [0.239, 0.259] | 41,416 | 29,264 | Size −29.3%; build ranges overlap |
| `bench/nbody.py` | 0.942 [0.924, 0.981] | 0.927 [0.908, 0.955] | 104,640 | 88,088 | Size −15.8%; build ranges overlap |
| `bench/spectral.py` | 1.047 [1.024, 1.084] | 0.845 [0.841, 0.848] | 108,272 | 87,632 | Size −19.1%; build −19.3%, ranges separate |
| `bench/pyperformance/richards.py` | 1.584 [1.511, 1.654] | 1.306 [1.243, 1.483] | 130,920 | 114,376 | Size −12.6%; build −17.6%, ranges separate |
| `bench/smoke/text.py` (opt-in) | 8.470 [8.206, 9.114] | 8.746 [8.395, 8.877] | 572,360 | 584,720 | Size +2.2%; build ranges overlap |

The text program opts in to dynamic `Any` and imports `fnmatch`, `json` and `re`.
It deliberately keeps the feature paths that the plain programs can discard.

## Execution checks

Whole-process wall-time medians in seconds, with ranges:

| Workload and arguments | Baseline JIT | Candidate JIT | Baseline AOT | Candidate AOT |
|---|---:|---:|---:|---:|
| hello | 0.0749 [0.0740, 0.0770] | 0.0764 [0.0756, 0.0818] | 0.00217 [0.00211, 0.00221] | 0.00216 [0.00212, 0.00219] |
| nbody, built-in 500,000 steps | 0.1766 [0.1536, 0.2018] | 0.1857 [0.1631, 0.2087] | 0.0451 [0.0342, 0.0508] | 0.0452 [0.0415, 0.0480] |
| spectral, built-in size 500 | 0.1408 [0.1375, 0.1619] | 0.1464 [0.1363, 0.1642] | 0.0197 [0.0148, 0.0250] | 0.0152 [0.0145, 0.0208] |
| richards, `50` | 0.4195 [0.3504, 0.4899] | 0.4393 [0.3935, 0.4730] | 0.0297 [0.0276, 0.0556] | 0.0377 [0.0279, 0.0386] |
| text, `fnmatch 1000` | 3.0113 [2.9063, 3.3299] | 2.9865 [2.8174, 3.2815] | 0.0310 [0.0295, 0.0415] | 0.0315 [0.0285, 0.0336] |

All execution ranges overlap. The richards short-run AOT loop median was initially
25.3% higher (0.02831 to 0.03548 seconds), so it was checked with a ten-times-longer
input rather than treated as harmless noise. Seven more interleaved pairs with
`500` runs did not confirm the slowdown:

| Richards 500-run AOT confirmation | Baseline | Candidate |
|---|---:|---:|
| In-process loop wall time | 0.3011 [0.2662, 0.3626] | 0.2953 [0.2696, 0.3079] |
| Whole-process wall time | 0.3032 [0.2678, 0.3645] | 0.2971 [0.2713, 0.3095] |
| Whole-process user + system CPU time | 0.3022 [0.2674, 0.3640] | 0.2966 [0.2708, 0.3091] |

The text control's loop medians were 0.03647 to 0.04058 seconds in JIT and 0.02692
to 0.02727 seconds in AOT; both ranges overlapped. These shared-host samples support
no confirmed execution regression, not an assertion that every workload is unchanged.
Cold-cache cost, peak memory and timing under GC stress were not measured here.

## Deterministic boundary checks

`tools/aotprobe.py` passed with the hosted candidate compiler on five programs:
plain, direct python-int, direct dynamic-Any, imported python-int and imported
dynamic-Any. The captured AOT module defined `pys_plain` as `1, 0, 0, 0, 0`.
The plain executable retained none of the seven symbol controls; both direct and
imported opt-in controls retained the expected helpers, and every executable's
output matched CPython. Explicit `mpz` use remains supported by its normal corpus
cases; this optimization does not remove helpers still used directly.

The aggregate gate's tests reject missing imported-program, symbol-count or compiler
evidence. All 67 verification-harness unit tests passed locally, including the 22
aggregate tests. The original prototype's complete CI run
[40764776286](https://github.com/den-run-ai/pystachy/actions/runs/40764776286)
also ran its original three-program AOT probe successfully in the contracts job.
That historical run does not certify the later five-program candidate; its exact
revision remains subject to the PR's applicable CI workflows.

## Reproduction inputs

Use separate checkouts and caches, a fixed CPU, the pinned Python and LLVM versions,
and the same source path for both compilers. Warm each runtime cache, compare JIT and
AOT stdout to CPython, then alternate which revision runs first. Build with
`python3.13 -m pystachy build SOURCE -o EXE` and run JIT with
`python3.13 -m pystachy run SOURCE ARGS` from each compiler's checkout, setting
`PYSTACHY_HOME` to that checkout. Clear inherited result-affecting settings and keep
`PYSTACHY_CACHE` separate for the two revisions.

| Source | SHA-256 |
|---|---|
| `print(1)` followed by newline | `cc42155088fca5730758db72b2a5bca33112a941dfaa2d43098ec422ce4ea213` |
| `bench/nbody.py` | `1c163e560eea0d5196202fd19cb43c6c59c8db335f1157cbdd252af0e1eebc7b` |
| `bench/spectral.py` | `0ba2115a31ca52d8b6a6d8949882c25bdce261ef8e756d976eb348c8cc11e0b0` |
| `bench/pyperformance/richards.py` | `f290fb528a0086dc5fd98bdf866c591252d8c8a31c80415c051a6ae69c7e0c82` |
| `bench/smoke/text.py` | `abcf4ba78bd62af42207230106b96f63b1a64758c1aa2831a49d0ba7781e6302` |

Run `python3.13 tools/aotprobe.py -c 'hosted=python3.13 -m pystachy'` for the local
boundary probe, or `make aotprobe` after bootstrapping to check both compiler tiers.
