# Integer-query boxing in graph processing — 22 October 2026 (Pacific)

PR #873 addresses most of graph regression G introduced by #821. PR #869 separately retains the graph processing guard. This branch is evidence only; do not merge its research directory.

## Result

Frozen `dynany_bench.py graph 4000`, checksum 670230. CPU 0, CPython 3.13.16, LLVM 18.1.3, private warmed runtime caches. Fifteen paired processes per revision/mode: two requested independent batches of five plus an automatic five-process confirmation in the first batch. Construction and compilation are excluded from processing CPU time; raw process/startup/RSS metrics remain available.

| Processing median | #821 parent f4b93961 | Current main 32d7c40b | Candidate | Change vs current |
|---|---:|---:|---:|---:|
| JIT | 51.483 ms | 76.327 ms | 57.939 ms | -24.1% |
| AOT | 49.027 ms | 69.467 ms | 55.908 ms | -19.5% |

Paired-bootstrap 95% ratios vs current: JIT 0.682–0.859; AOT 0.696–0.921 (20,000 resamples, fixed seed 731). Against the historical parent, median residual overhead is 12.5% JIT / 14.0% AOT; intervals 1.007–1.267 / 1.036–1.294 still span the 20% threshold. Thus the large regression is substantially reduced; complete historical recovery or a precise residual bound is not established on this variable shared host. Individual batches and raw samples are retained, not selected by favorable outcome.

## Mechanism and safety

Untimed instrumented AOT processing counters fall from 284,000 to 144,000 heap integer boxes (49.3% fewer). The pure lookup handles 288,000 queries, with zero generic fallbacks in this graph workload. Reference boxing is unchanged at 356,000. Table hashes, layout and probe sequence are unchanged; address-dependent slot totals fluctuate slightly and are not a claimed probe-count reduction.

The helper searches with the raw integer, returns an entry or absence, and stops before any matching non-int/bool comparison. The caller then boxes its original value and executes the original lookup. Stored keys still keep their boxes. The C probe verifies no allocation/mutation/callback on the pure helper; Python regressions cover mixed keys, numeric collisions, query identity retention, callback mutation/restart, exceptions, and evaluation order.

Native compiler/runtime fixed points passed. The full 3,533-program IR oracle changes only five intended inputs, with no acceptance/diagnostic differences. The oracle shares the current runtime/library home because those imported library inputs are identical at the base; generated runtime code is separately checked by native differential tests. Runtime signatures/effects and dictionary probes pass, including GC stress. The original new C test expected one callback for hash 1000; its expectation was corrected to two, because the unchanged CPython-style sequence visits slots 0, 0, 1.

All 124 Dynamic Any cases pass native JIT/AOT in both normal and GC-stress modes (496 checks). Independent review completed 16 additional native executions across baseline/candidate, JIT/AOT and normal/GC stress. Pure-to-callback transitions and retained local query identity match CPython.

Local Ruff, C warnings, GC root lint, shell lint and repository hygiene pass. Full recording verification passes in CI. Local full-recording attempts first lacked `typing_extensions`, then used a venv with a `sys.base_prefix`/`sys.base_exec_prefix` mismatch (one recording difference); these setup-specific failures are retained in the logs and are not labeled successful runs.

Independent review also reconfirmed a pre-existing typed-argument identity deviation covered by #858; baseline and candidate give identical output. This optimization does not repair that calling convention. Dynamic Any stays experimental/opt-in.

## Provenance and replay

Raw timing used local commit `199d50fe` (tree `3f29caf7`); the published implementation is `7509f866530f67de2d20dd724b2ab352b8f6863e`. `provenance.json` records exact hashes and verifies compiler/runtime/library sources are identical. Only test/guard files changed after the measured implementation. Native builds were fresh; the historical parent binary retains the previous campaign's recorded identity.

`manifest-recorded.json` preserves original paths and identities; do not overwrite it. With a clone containing the public commits and a complete LLVM 18.1.3 toolchain, run `prepare_replay.py --repo REPO --output NEW_DIRECTORY --llvm LLVM_BIN --python PYTHON_3_13_16 --library-path LLVM_LIBS`, then its printed runner command. It rebuilds native compilers from published sources in isolated worktrees and records a new cohort. The supplied Python and LLVM versions must match; replay hashes describe the supplied binaries and are not presented as the original toolchain bits. Keep other heavy work idle.

The replay preparation helper was independently checked for executable/path resolution, tool and workload hashes, revision mapping, fresh-directory behavior and invalid-input handling; no new timing run was performed during that check.

`instrument_graph_nobox.py` and `run_graph_counters.py` preserve the separate untimed mechanism study. The latter records input Git/source/compiler hashes and refuses dirty source trees. Update its source paths explicitly for a new checkout; instrumentation timing is not evidence of speed.

The earlier hosted-compiler exploratory pairs are retained separately. A direct int/bool `hdyn` specialization was tested after the guarded lookup but showed no repeatable improvement (59.535 vs 59.804 ms); it was discarded and is absent from the PR.
