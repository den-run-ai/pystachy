# List shape effects

This experiment preserves a captured list-length proof across audited element
and identity writes. It retains the ordinary write/allocation/exception effects,
and reloads elements after a write. Resizing, raw writes, unknown calls, and
generator suspension keep checked fallbacks.

`kernel.py` repeatedly updates a numeric list and reads each element before and
after its update. Its read-only mode is a control. This is a focused compiler
benchmark, not an end-to-end ndarray, SciMark or nanoGPT result.

## Measurements on the final stack

Baseline: semantic list-contract draft #1128,
`1dc2a4bb3db43a5c0f1e8ab02b12c8aeecd5fb9d`, built from the identical compiler
source at local `4fd481b0`. It already includes #1125's bounded range proof.
Candidate compiler: local `1e4359a0cffd15fc330c9038cb75163a063f5c3f`, adding
shape effects to the same contracts. Later report edits do not change compiler
source. Published file trees are verified against these local sources.
Linux x86-64, AMD EPYC 9V74, LLVM 18.1.3, CPython 3.13.16. Shared host,
processes pinned to CPU 0; nine alternating pairs after one warmup per variant.
Each sample covers 8,192 elements and 10,000 rounds (81,920,000 iterations).
Every output and stderr was checked against the same source run by CPython.
Other team builds and tests were paused during timing.

| Mode / workload | Baseline median | Candidate median | Result |
|---|---:|---:|---|
| Warm JIT / updates | 0.581667 s | 0.347644 s | 1.67x faster; all nine pairs improve |
| Warm JIT / read-only control | 0.118393 s | 0.130961 s | 10.6% higher process time; eight pairs regress |
| AOT / updates | 0.074876 s | 0.076932 s | 2.7% higher median; overlapping ranges |
| AOT / read-only control | 0.074790 s | 0.074204 s | Overlapping ranges; no established gain |

These are process wall times. Warm JIT includes frontend compilation, LLVM JIT
work and execution, with a warmed runtime cache; it is not an isolated kernel
timer. AOT times include process startup and execution, excluding compilation.
The JIT runtime remains a separate library; AOT can already inline and optimize
the checked runtime accesses. No AOT acceleration is established here. The update
JIT ranges do not overlap (0.556–0.611 s before, 0.336–0.390 s after).

The read-only JIT control is a material qualification: its process median regresses
even though it does not perform element updates. The program contains both kernels,
and these times include compiling and JIT-loading that program, not only executing
the selected loop. Native IR comparison confirms `read_only` is byte-identical
(1,977 bytes); the module differs only in `update`, by six lines and 264 bytes.
The driver compiles the full program before collecting its run arguments, so the
control still compiles the changed update body. This establishes a possible
overhead path, not the measured cause of the regression. Do not call the read-only
result a tie or claim uniformly lower compilation/execution cost.

[AOT samples and binary/source hashes](results/aot.json) and
[JIT samples and compiler/source hashes](results/jit.json) retain all timings.
[Native IR comparisons](results/ir.json) retain the source/compiler hashes and
complete code-shape findings for both kernels and the standalone regression.
The AOT executables are both 90,760 bytes. The standalone `updated` regression
changes two checked reads to two inline loads, with its intervening store intact.
Its raw function IR grows from 53 to 59 lines; the optimization is not an IR-size
reduction. The native compiler fixed point grows 834,585 to 834,805 lines,
while runtime IR remains 18,805 lines.

## Reproduce

Use separately built baseline and candidate compilers with LLVM 18 selected:

```sh
BASELINE/pystachy build bench/list_shape/kernel.py -o /tmp/list-shape-old
./pystachy build bench/list_shape/kernel.py -o /tmp/list-shape-new
python3 bench/list_shape/compare.py /tmp/list-shape-old /tmp/list-shape-new \
  --pairs 9 --rounds 10000 --output /tmp/list-shape-aot.json
python3 bench/list_shape/compare.py BASELINE/pystachy ./pystachy --jit \
  --pairs 9 --rounds 10000 --output /tmp/list-shape-jit.json
```

Do not overlap timing runs with builds or tests. The runner verifies every
sample and fails on a nonzero exit, unexpected stderr or differing output.

## Validation

At the final compiler source: compiler/runtime three-stage fixed points, `make
check-fast` (426 tests), 36 focused native JIT/AOT checks, twelve program-only
GC-stress checks and six disabled-`listget` controls passed. The runtime audit
passes all 644 entries and 172 subset functions. Full lint passes; a separate
global-container audit accepts the trusted tables' ownership classifications. Hosted regressions
retain checks for shrinking aliases, arbitrary direct/indirect calls and growth;
they require distinct loads around an element write. Repository hygiene and
Ruff passed. Full local `make verify` was not run.

An independent runtime audit checked all ten primitive contracts. Adversarial
hosted probes retained checked reads after nested-owner replacement, field
rebinding, handler-driven alias shrinkage and induction-variable changes. A
temporary stack with the optional-slot, tuple-construction and callback-cloning
drafts passed 104 focused hosted tests. Its combined probe preserved range
metadata in both specialized callback variants, reloaded after an element update,
kept an optional minimum unboxed, and directly constructed the final tuple.
This integration evidence is hosted; it is not a full combined native gate.

The full native IR oracle compares 4,243 frozen-input cases against #1128:
2,363 accepted programs and 1,880 expected rejections, with no status changes.
The original separate-home run has 261 path-only differences and four intended
code differences. All 265 changed cases were rerun with a common home after
verifying identical libraries/runtime: 261 became byte-identical, and the same
four code differences remained. They contain exactly eleven checked-read
substitutions at the original result, owner, index and position; no other
instruction changes were found. Data-dependent and unrelated-owner reads remain
checked. The compiler and runtime corpus outputs are byte-identical.

All four changed programs also pass native JIT/AOT execution. The nanoGPT
difference is in a test assertion helper, not its model kernels. These details
and every affected function are in [the corpus report](results/corpus.json);
[validation commands and counts](results/validation.json) separate the IR oracle
from execution, GC, disabled-pass and timing checks. The original oracle's path
differences remain recorded; no LLVM string literals were normalized away.
