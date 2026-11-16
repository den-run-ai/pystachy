# Compiler-stage qualification on alpha.4

PR [#1499](https://github.com/den-run-ai/pystachy/pull/1499) merged into v0.5.0-alpha.4
passes every outstanding qualification check, and no defect was found. Every result below
applies to tree `c8fa5a1f6bf8bd5dd3a6d8eddcd499a58d6a67ed`. GitHub's test merge `79f5d0be`
of PR head `d266e919` into main `3da553ee` has that tree. So does `bb04e196`, the alpha.5
integration merge on `claude/serene-mendel-ht4lna`. The reference compiler is alpha.4,
`3da553ee`, built with `make ref` from that commit's sources.

Local runs, on November 16, 2026, used 4 x86-64 cores, Ubuntu clang and LLVM 18.1.3, and
Lean 4.35.0 from `tools/setup_lean.py`'s verified archive. The local CPython was 3.13.18;
`.python-version` pins 3.13.16. CI used the pinned CPython.

## Results

| Check | Result | Record |
|---|---|---|
| Full-profile CI | [Run 43809511213](https://github.com/den-run-ai/pystachy/actions/runs/43809511213) passed 73 jobs; the PR-only sampling matrix was skipped by design. Each `make verify` aggregate passed 58/58 steps on x86-64 and on ARM64. | [summary](results/ci-x86-verification-summary.json) |
| Corpus parity | `tools/irsame.sh` with one shared `PYSTACHY_HOME`: all 4,796 programs have identical IR, diagnostics and exit status. With separate homes, 4,497 are identical; the other 299 differ only in the library path embedded in `ImportError` message constants. | [shared](results/irsame-corpus-shared-home.log), [separate](results/irsame-corpus-separate-homes.log) |
| FFI outside the corpus | `irsame` over `tests/ffi`, its `ir`-mode rejections and the extern, ctypes and pyobj examples covers 158 programs: 76 compile and 82 are rejected. All match; three of them differ only in that library path and are byte-identical with a shared home. | [files](results/ffi-irsame-files.txt), [log](results/ffi-irsame-separate-homes.log), [recheck](results/ffi-shared-home-recheck.txt) |
| Extension mode | The hosted harness covers 22 programs: the LLVM of 14 extension modules and the diagnostics of 8 extension rejections are identical. | [results](results/ext-compare.json) |
| Bootstrap | `make` reached fixed points: compiler IR 961,586 lines, `runtime.py` IR 21,214 lines. | [log](results/make.log) |
| Hosted tests | 60 stage and inspection tests, 18 frame-field tests and 7 lljit tests passed. `make check-fast lint` ran 43 unittest invocations with 1,232 tests. Retained IR with real LLVM (10), bootstrap tier (8), and verification and compiler-state controls (138) also passed. | [stage](results/stage-tests.log), [lint](results/check-fast-lint.log), [extra](results/lint-extra.log) |
| Lean | `lake build` completed 50 jobs, and 63 axiom audits passed. All 33 `test_lean*.py` files passed with `LEAN_BOUNDARY_REQUIRED=1`: 486 tests, no skips. | [build](results/lake-build.log), [tests](results/lean-tests.log) |
| Ten-program Lean report | Both commits proved 526/526 obligations or uses, with nothing rejected or unsupported, and their tables are identical. | [bb04e196](results/lean-report-bb04e196.md), [3da553ee](results/lean-report-3da553ee.md) |
| Self-compilation cost | All outputs were identical. Peak RSS fell 3.5 MiB (−0.37%) and the binary grew 16,536 bytes (+0.23%). Callgrind counted 9.4 million more instructions (+0.042%). Wall time is inconclusive. | [cost](results/cost.json), [callgrind](results/callgrind.txt) |

## Methods

The extension harness, [`scripts/ext_ir_compare.py`](scripts/ext_ir_compare.py), runs each
root's `driver.compile_program(path, source, dirs, ext=<stem>)`. It uses the directories
that `driver.main` computes and a clean `PYSTACHY_*` environment. It compares stdout,
stderr (normalizing only the root's own path prefix) and exit status. The inputs are
`tests/ffi/ext/*.py` modules that `tests/ffi/run.sh` builds, plus
`tests/ffi/errors/ext_*.py`. `tools/irsame.sh` compiles only in `ir` mode, so it never
reaches export admission.

A shared library home is valid only because `git diff 3da553ee bb04e196 -- lib runtime.c
runtime.py mpz ryu` is empty and `build/ref/lib` equals `lib/`. Otherwise each compiler
embeds its own home in the absolute path of an `ImportError` message.

[`scripts/cost.py`](scripts/cost.py) times `COMPILER ir pystachy.py` from the merged
checkout, pinned with `taskset -c 3`. After one warm-up run per compiler, it runs 12 rounds
in alternating order and reads peak RSS from `wait4`. Median wall time was 5.119 s for the
merged compiler and 5.030 s for alpha.4. The median paired difference was +0.118 s, the
merged compiler was slower in 8 of 12 pairs, and per-run σ was about 0.33 s, so the
timing difference is inconclusive. Callgrind ran each compiler once on separate cores and
counted 22,437,058,311 instructions for the merged compiler against 22,427,672,829 for
alpha.4.

The ten-program report repeats the selection in
[`5ccd1841`'s report](https://github.com/den-run-ai/pystachy/blob/8514c4b34db93ef17d7f315f3225560e906b8934/research/compiler-stage-completion-2026-11-15/lean/final-head/report.md),
with `tools/lean_report.py PROGRAMS --output ... --records ...`. Promoting-int storage
fell from that report's 116 obligations to 107, and alpha.4 also has 107, so the drop
predates #1499. The merged tree's reporter stops after `finalize` and alpha.4's lowers;
both give the same table.

## Limits

These runs did not include a local `make verify`, since CI ran the full profile, or
`make check-recordings`, because this PR changes no recordings and the local CPython is
not the pinned one. The full Lean census is being produced by the alpha.5 integration.
CI's Lint workflow has not run on the merged tree; the local `check-fast lint` and the
Lean runs above replace it here. Preparation and discovery still couple typing,
representation selection and specialization, and `pystachy check` remains parse-only.

Prepared with Claude Code.
