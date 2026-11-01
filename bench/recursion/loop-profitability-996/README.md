# PR #996 loop-profitability evidence

Start with the [decision report](../../../docs/reports/recursion-guard-loop-profitability.md). The source PR is [#996](https://github.com/den-run-ai/pystachy/pull/996). This is a separate research branch: **do not merge these archives or unapplied patches into the source PR.**

## Revisions and scope

| Measurement role | Revision / contents |
|---|---|
| `main` | `07b26e02425d023288ed95a9d2a5077be5aeb45e` |
| `baseline` | Previous PR `ea68529b8a590eb8f3df7200b857e1d16becd7a3` |
| `value` | ea685 plus the rejected scalar-depth patch |
| `policy` | First policy `1ff5efe4c4425b3728e138fa05a44856202fdea5` |
| `policy_final` | Current source `44b638bbf8df1835b67bebda0468d65374569c71`, tree `a1eddfe2c43d368b5c48ac79798501d8d7add552` |

The final code changes only the profitability predicate, two hosted test modules and two compiler contract documents relative to ea685. Runtime ABI and compatibility policy are unchanged. The scalar prototype was rejected after a 7.686% object-call instruction increase and did not receive full bootstrap/CI validation. The first policy failed the existing nested-loop IR expectation; the final refinement restores it without changing the golden. Historical failures remain recorded.

## Readable indexes and raw evidence

| Location | Contents |
|---|---|
| [Initial index](local/evidence-index.json) | Original main/ea685/scalar/first-policy experiment; compact archive/hash index |
| [Initial archive sizes](local/archive-sizes.json) | Eleven immutable initial archives, plus metadata addenda |
| [Initial strict comparison](local/corpus-policy/comparison-summary.json) | Compact first-policy verdict; exact full JSON in `comparison.json.gz` |
| [Final index](final/local/evidence-index.json) | Final-role results, archive/member mappings and exclusions |
| [Final CI](final/ci/) | Final job ledger, independent 31-report remerge, source/bootstrap, lint, coverage and performance evidence |
| [First-policy CI](initial-ci/) | Historical failed-head ledger and relevant failed logs, separately identified |
| `scripts/` | Four exact controllers for the initial experiment |
| `final/scripts/` | Final-role measurement controllers, native JIT timing and focused native controller |
| `local/` and `final/local/` | Readable result records, source/binary identities and patches |
| `archives/` and `final/archives/` | Raw profiles, logs, IR evidence and recorded compiler output |

Initial archives total 35,706,369 bytes. They are unchanged by the later packaging cleanup. `local/artifact-manifest.json.gz` preserves the exact detailed manifest; `local/corpus-policy/comparison.json.gz` preserves the exact full strict-comparison record. The readable summaries include the original-byte hashes. Gzip compression is a storage transformation, not a change to a verdict.

### Initial archives

- `aot-main`, `aot-baseline`, `aot-value`, `aot-policy`: whole-process AOT Callgrind evidence and generated IR; disassembly is in the analysis archive.
- `jit-main`, `jit-baseline`, `jit-policy`, `jit-common`: actual-driver LLVM-tool profiles, captured optimized input, wrappers, command/raw-stream records and input/cache identity joins. Whole `lli` includes compilation and execution/runtime/GC/teardown.
- `analysis`: profile attribution and inspection records. Exclusive costs are not mixed with inclusive call edges.
- `run-records`: remaining initial raw preparation and control records.
- `corpus-policy.tar.xz`: original strict-failure evidence, recorded compiler streams and changed IR. The full top-level comparison JSON is the separately indexed gzip addendum.

The solid corpus archive expands 496 original `.ll.gz` files into their exact recorded LLVM bytes, allowing cross-file compression. Fourteen original plain-IR aliases are byte-identical and map explicitly to the same members. All original hashes, expanded payload hashes, sizes, modes and mappings are retained. The original failed verdict and diagnostic proof are unchanged. See [the transformation record](local/corpus-packaging.json).

### Final archives

Final archives are separately named under `final/archives/`; they do not replace initial evidence:

- `aot-policy_final.tar.gz`: final fnmatch and ordinary/object/JSON AOT profiles and associated raw artifacts.
- `jit-policy_final.tar.gz`: final hosted-driver user-`opt`/whole-`lli` profile and exact captured bitcode.
- Native-JIT attempt archives: each preparation/timing attempt retains its own original status and every observation. An incomplete attempt is not an elapsed comparison.
- `native-validation.tar.gz`: final native bootstrap/strict-standard-comparison logs and focused execution records.
- `run-records.tar.gz`: raw logs for final preparation, controls and six-order AOT timing. The associated JSON, including `reference-binaries.json` and the complete six-order timing record, is directly under `final/local/`.
- `corpus-final.tar.xz`: final recorded 3,924-case comparison, with exact raw compiler output and a separately identified diagnostic-only assessment.

The final index is authoritative for exact filenames, member paths and metadata sidecars. Generated native executables and runtime-cache objects are omitted with hashes and build/source bindings retained. Temporary signed download URLs and credentials are excluded. Published records retain their original absolute paths to make provenance and path-only diagnostics inspectable.

## Reproduction layout

Use a fresh workspace; do not overwrite published observations. Place original `scripts/` at `prototype-996/` below the workspace and final controllers at `prototype-996-final/`. Create sibling checkouts `pystachy-main`, `pystachy-baseline`, `pystachy-value`, `pystachy-policy` and `pystachy-policy-final` at the revisions above. Apply the scalar patch only to `value`. The full final-policy patch applies to ea685; the smaller loop-exit patch applies to 1ff.

Provide CPython 3.13.16 and pinned development requirements at `toolchain/venv/`, LLVM/Clang 18.1.3 at `/usr/lib/llvm-18/bin`, and Valgrind 3.22.0. Native timing/focused controllers additionally name the standalone interpreter `toolchain/python/cpython-3.13.16-linux-x86_64-gnu/bin/python3.13`. Recreate that layout or retain an explicit controller adapter and new hashes as a new experiment.

Run one heavy job at a time. Build fresh AOT references for a reproduction; the original final series reused byte-identical earlier binaries, explicitly bound in `reference-binaries.json`.

```sh
toolchain/venv/bin/python prototype-996-final/measure.py prepare main baseline policy_final
toolchain/venv/bin/python prototype-996-final/measure.py profile main baseline policy_final --n 10000
toolchain/venv/bin/python prototype-996-final/kernels.py main baseline policy_final
toolchain/venv/bin/python prototype-996-final/measure.py time main baseline policy_final --n 100000
toolchain/venv/bin/python prototype-996-final/jit_measure.py main baseline policy_final --n 1000 --output prototype-996-final/jit-replay
```

All roles consume the same `pystachy-baseline/bench/smoke/text.py`; outputs are checked against pinned CPython. The AOT controller retains all six role permutations. Native timing uses the final compiler and its ea685 `build/ref` reference, real LLVM, separate homes/caches, CPU 0, one build/reuse warm phase and six AB/BA pairs. It records wall/CPU and in-program loop timing separately and rejects invalid preparation before collecting samples.

For native validation, put the pinned venv first on PATH, use the recorded LLVM and bounded `PYSTACHY_JOBS`, and run the repository's build and required CI matrix on the final tree. `make irsame REF=ea68529b8a590eb8f3df7200b857e1d16becd7a3` bootstraps the current compiler and prepares/reuses its pinned reference, then invokes the unmodified strict oracle. Intentional IR changes still produce a failed strict result.

The additional recorder preserves the standard 3,920 cases plus exactly four recursion benchmarks:

```sh
toolchain/venv/bin/python prototype-996-final/corpus_compare.py --root pystachy-policy-final --output prototype-996-final/corpus-replay --workers 4 --include-recursion-benchmarks
toolchain/venv/bin/python prototype-996-final/focused_native.py --output prototype-996-final/focused-replay
toolchain/venv/bin/python prototype-996-final/jit_time.py --output prototype-996-final/jit-native-replay
```

Both comparison compilers use their own verified library homes. The independent diagnostic assessment proves only specific checkout-path byte spans against pinned, byte-identical files. It does not turn byte-different LLVM into a strict pass or establish semantic equivalence for every possible program.

## Interpretation and remaining hold

Final instruction/code-volume reductions and final CI success are distinct from elapsed performance acceptance. The final local AOT timing did not show an improvement over ea685. Both native-JIT preparation attempts failed before timed pairs and remain explicit limitations in the decision report and attempt records. CI's advisory performance threshold is not an agreed budget for this PR. No samples are discarded or pooled across source checkpoints/runners, and no compatibility reduction or guard-free implementation is claimed.
