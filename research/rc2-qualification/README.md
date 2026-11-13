# RC.2 qualification evidence — 2026-11-13

This research snapshot records the local comparison and focused execution checks for the RC.2 corrections in PRs [#1411](https://github.com/den-run-ai/pystachy/pull/1411) and [#1419](https://github.com/den-run-ai/pystachy/pull/1419), including the narrow string-prefix/suffix change from [#1332](https://github.com/den-run-ai/pystachy/pull/1332). It is evidence for those corrections, not a claim that all v0.4.0 stable-release criteria are complete.

## Source identity

| Role | Commit | Tree |
|---|---|---|
| Comparison baseline | `63e4e52d298ab21ece81d99aef60b5d4bf0ee764` | `2b06c58a6fe0b41b6240190e750add7bb3c85237` |
| Locally qualified candidate | `c2da5cfffbe250106cf59576c756e6cdd2c25649` | `1281c9b2b04f4134c9bb6a3046e6d1d80907ceff` |
| PR #1419 CI synthetic merge | `4244685db375a013d53aa1f9a21d69283ab33ecd` | `1281c9b2b04f4134c9bb6a3046e6d1d80907ceff` |
| Merged main, PR #1419 | `bf699eb5ba0bc8ba2371f4d1740683be59594f58` | `1281c9b2b04f4134c9bb6a3046e6d1d80907ceff` |

`git show -s --format='%H %T'` verified the three equal candidate trees. [source-identity.json](source-identity.json) records the mapping. Local results below were produced on the candidate commit; post-merge exact-main gates were still running when this snapshot was prepared. The research commit is based on the candidate and adds only this evidence directory.

## Recorded results

| Check | Result |
|---|---|
| Baseline bootstrap | Compiler fixed point across 3 stages, 915,570 IR lines; runtime fixed point, 21,214 lines |
| Candidate bootstrap | Compiler fixed point across 3 stages, 915,671 IR lines; runtime fixed point, 21,214 lines |
| Full native IR comparison | 4,493 cases; 4,132 byte-identical, 321 checkout-prefix-only, 40 material differences |
| Acceptance and infrastructure | 0 new rejections, 8 intended new acceptances, 0 infrastructure errors |
| Candidate focused native JIT/AOT | 334 cases, 556 passed checks, 0 failed |
| Candidate focused program-GC stress | 13 cases, 26 passed checks, 0 failed |
| Candidate focused hosted JIT/AOT | 14 cases, 27 passed checks, 0 failed |
| All 39 changed non-benchmark cases | 77 passed checks, 0 failed; repeated under program-GC stress with the same result |
| Logging benchmark correctness | 32 loops; CPython, JIT and AOT all returned `logging 32 16320` and exit 0 |

Counts distinguish cases from checks: an expected compile rejection contributes one check, while an executable case normally contributes JIT and AOT checks. The changed-case set is in [changed-cases.txt](changed-cases.txt). It includes the changed rejection and excludes `bench/pyperformance/bm_logging.py`, checked separately.

The two compilers emitted byte-identical IR for the same candidate `pystachy.py` and `runtime.py` inputs. That does not conflict with the different bootstrap line counts: each bootstrap compiled its own source revision.

Every material difference was adjudicated in [comparison/adjudication.json](comparison/adjudication.json). Eight valid programs become accepted (one generator union payload and seven generic signature/global cases). Other changes are consistent specialization/helper renumbering, later method emission, removal of unused internal methods and associated constants, one legitimate `Box.def` readiness guard, and one preserved type rejection with shorter context. The difficult collections comparisons were closed against every retained function body, including call targets and recursively expanded TBAA identities; explicit mappings are in [review/](review/). These review aids do not change the strict comparison classifications. [The final seven-case logging review](review/logging-final-review.json) also records complete metadata/global/reference checks. The separately named preliminary logging script/output cover only six cases and strip TBAA; they are historical intermediate evidence, not a reproduction of that final review.

## Comparison method and reproduction

The toolchain was CPython 3.13.16 with LLVM 18.1.3 on Linux x86_64. Use the same versions, fresh clean checkouts, and two workers. The original environment paths are preserved in [logs/rc2-env.sh](logs/rc2-env.sh); adapt those paths on another machine.

The [comparison harness](retained_ir_compare.py) uses exactly the default `tools/irsame.sh` inventory: compiler, runtime, `tests/programs/*/*.py`, deviations, benchmarks, IR cases, and expected errors. Each binary receives its own `PYSTACHY_HOME`, library and runtime. Both compile the same candidate inputs from the candidate working directory. The harness uses `tests/prepare_path.sh` for `.path` sidecars, including the bracket-path fixture, and uses runtime mode for `runtime.py` and `rtmode_*.py`.

Only the exact baseline checkout prefix is replaced with the equal-length candidate prefix on a separate comparison copy. Raw outputs are never rewritten. No symbol, string, metadata, line-number, error-message or other normalization is used by the oracle. The 321 path-only cases comprise 251 accepted IR files and 70 rejected diagnostics. All tracked source files, selected inputs/sidecars, binary hashes and exact heads are checked before and after the run; none changed.

From an existing repository clone, with `WORK` an empty scratch directory and `EVIDENCE` pointing to this evidence directory in a separate checkout:

```bash
BASE=63e4e52d298ab21ece81d99aef60b5d4bf0ee764
CANDIDATE=c2da5cfffbe250106cf59576c756e6cdd2c25649
WORK=/absolute/path/to/qualification
EVIDENCE=/absolute/path/to/research/rc2-qualification
export PY=/path/to/python3.13
export PYSTACHY_LLVM=/path/to/llvm18/bin
export PYTHON="$PY"
export PATH="$(dirname "$PY"):$PYSTACHY_LLVM:$PATH"
export PYSTACHY_JOBS=2

git worktree add --detach "$WORK/baseline" "$BASE"
git worktree add --detach "$WORK/pystachy" "$CANDIDATE"
(cd "$WORK/baseline" && make PY="$PY")
(cd "$WORK/pystachy" && make PY="$PY")

"$PY" "$EVIDENCE/retained_ir_compare.py" \
  --base "$WORK/baseline" --candidate "$WORK/pystachy" \
  --base-sha "$BASE" --candidate-sha "$CANDIDATE" \
  --output "$WORK/comparison" --workers 2 --llvm "$PYSTACHY_LLVM"
```

The harness intentionally returns exit 1 when material differences exist, even when later review explains them. It returns 2 for an incomplete, unstable or infrastructure-failed comparison. Review every difference before interpreting the result. `baseline` and `pystachy` have equal byte lengths; other checkout names must preserve that condition. A new output directory is required.

The candidate-focused execution commands, run from the candidate checkout, were:

```bash
make test FILES='tests/programs/generics/*.py tests/errors/generics/*.py tests/programs/generators/*.py tests/programs/strings/*.py'

PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' \
  tests/programs/generics/generic_signature_*.py \
  tests/programs/generics/generic_return_repr_global.py \
  tests/programs/generics/generic_annotations.py \
  tests/programs/generics/generic_mod_default.py \
  tests/programs/generators/gen_yield_union_payload.py \
  tests/programs/strings/str_affix_bounds.py

make test-py FILES='tests/programs/generics/generic_signature_*.py tests/programs/generics/generic_return_repr_global.py tests/programs/generics/generic_annotations.py tests/programs/generics/generic_mod_default.py tests/programs/generators/gen_yield_union_payload.py tests/programs/strings/str_affix_bounds.py tests/errors/generics/generic_signature_repr_bad.py'

mapfile -t CHANGED < "$EVIDENCE/changed-cases.txt"
tests/run.sh ./pystachy 'jit aot' "${CHANGED[@]}"
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' "${CHANGED[@]}"

PYSTACHY_PROGRAM_CACHE=0 PYTHONHASHSEED=0 \
  "$PY" tools/bench_pyperformance.py --compiler ./pystachy \
  --benchmarks logging --runs 1 --json "$WORK/logging-check.json"
```

## CI timing and bounded performance evidence

[ci/audit.json](ci/audit.json) and compressed job/step records cover full-profile main run [43365856650](https://github.com/den-run-ai/pystachy/actions/runs/43365856650) at `3bfd889b` and candidate PR run [43366916755](https://github.com/den-run-ai/pystachy/actions/runs/43366916755). The latter ran synthetic merge `4244685d`. Both completed successfully with one intentionally skipped job; maximum job execution times were 693 and 678 seconds, respectively, below 720 and 900 seconds. Queue/dependency waiting is excluded. Artifact reports identify the sampled CPU as `znver3` and preserve toolchain/source identity.

The sampled `gc-self` stage times were 289.145 and 290.450 seconds, below 360 seconds (60% of the unchanged 600-second guard). These are individual source-size observations. They do not prove the repeated representative CPU runs, full Variants coverage, or at-most-linear source-size scaling required by [#1178](https://github.com/den-run-ai/pystachy/issues/1178), [#1179](https://github.com/den-run-ai/pystachy/issues/1179), and [#1181](https://github.com/den-run-ai/pystachy/issues/1181). A separately retained Variants artifact is included as source evidence without upgrading those conclusions.

[performance/affix-benchmark.json](performance/affix-benchmark.json) measures only the isolated prefix/suffix change, comparing `63e4e52d` with the performance worktree revision `6c2b56fa`; [the isolated patch](performance/affix-worktree.patch) preserves that source delta. Fifteen interleaved, CPU-pinned AOT subprocess samples on one machine gave median 67.001 ms before and 62.224 ms after (7.13% less time), with identical program IR and output. Both recorded 2 GC collections and 59.1 MiB peak heap. This does not establish a full-release performance result or resolve the historical GC portion of [#1301](https://github.com/den-run-ai/pystachy/issues/1301). The logging sample is a correctness check; its single timing is not a performance claim.

## Evidence inventory and limits

- [comparison/summary.json](comparison/summary.json), [metadata.json](comparison/metadata.json), and [adjudication.json](comparison/adjudication.json) preserve counts, source/binary hashes, environment, and every differing case. `comparison-summary.json` is the original machine summary before semantic adjudication.
- `comparison/result-hashes.tsv.gz` preserves stdout/stderr/IR existence, size and SHA256 for all 4,493 cases. Compressed inventory and both full tracked-source manifests preserve input/sidecar/source hashes. Read them with `gzip -dc`.
- [logs/](logs/) contains both bootstrap logs and all requested focused, hosted, changed-case, program-GC-stress and logging logs. [execution/logging-correctness.json](execution/logging-correctness.json) includes exact source/binary identity and all three outputs.
- [ci/artifacts/](ci/artifacts/) contains the retrieved verification/Variants JSONs and their original ZIPs. Temporary signed download URLs are deliberately omitted.
- [SHA256SUMS](SHA256SUMS) covers all packaged files except itself.

**Raw per-case stdout, stderr and IR are not durable in this research branch.** They remain in the transient scratch directory `/workspace/scratch/2446eb38e476/rc2-retained-comparison/cases/`, where every raw difference was retained for review. No raw 19 MB compressed material-case archive is uploaded. Reproduce them with the pinned inputs and harness above; hashes and decisions are durable here, while raw path references in the JSON are historical local paths. The supplementary review scripts retain their original local-path assumptions and require path adaptation after reproducing the raw data.

This package does not certify post-merge packaging, publication, all-platform installation, or all stable-release gates. IR comparison alone does not exercise the runtime C fast path; the native execution, Unicode checks and bounded benchmark provide separate evidence. The pre-existing circular-from-import issue [#1398](https://github.com/den-run-ai/pystachy/issues/1398), including optional-import-handler preservation, remains outside these changes.
