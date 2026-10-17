# Compatibility audit — 2026-10-17

Pystachy already runs useful selected stdlib APIs and the repository's adapted
PyPI workloads as native programs. It is not yet a drop-in interpreter for
arbitrary PyPI packages, `pyperf`, `pytest`, or CPython's full test suite.
An import compiling, an adapted workload passing, and an upstream suite passing
under CPython are three different results.

## Revision and scope

Measurements use main **`d3fbfc6f`**, CPython **3.13.16**, LLVM **18.1.3**, Linux
x86-64. The popular-package probes explicitly identify the few CPython 3.12.14
reference runs. The bootstrap reaches compiler and runtime fixed points:
**607,640** and **17,615** IR lines respectively. Early native checks used
`build/pystachy1`; later checks use the final `./pystachy`. Both were built from
this source revision and participated in that fixed-point check.

This is a bounded, reproducible survey of the shipped ports, the CPython stdlib
installation, 52 selected pyperformance sources, and named upstream packages.
It is not a percentage estimate for all of PyPI. The first rejection may hide
further blockers. Import and census success mean IR generation, unless an
execution check is explicitly reported.

| Area | Evidence and interpretation |
|---|---|
| Stdlib imports | **141/476** isolated imports compile; **46** upstream files are excluded because `lib/` supplies their top-level package/module. No timeout or crash. The exact 522-file inventory is retained. |
| Missing C modules | Throwing stand-ins raise the count only to **145/476**; only four extra imports succeed. This is dependency diagnosis, not working implementations. |
| Shipped stdlib APIs | **501 checks pass** over 322 selected files: 356 positive JIT/AOT checks, 143 expected rejections and 2 documented-deviation checks. See the [stdlib report](compatibility-2026-10-17-stdlib.md). |
| Adapted PyPI libraries | The 15 shipped ports' **31 workload programs pass in JIT and AOT (62 checks)**; see the unmodified-source comparison in the [package report](compatibility-2026-10-17-packages.md). |
| pyperformance | **18 delivered adaptations**; **6/52** upstream sources compile with only the pyperf runner replaced. These overlap; do not add them. Execution results and advisory timings are in the [benchmark/suite report](compatibility-2026-10-17-benchmarks.md). |
| Upstream suite preservation | Unedited fnmatch/textwrap suites run against the edited files under CPython: **83 passed**, no skips. This is separate from compiled upstream-derived case coverage. |
| General suite runners | Native `unittest`, `pytest`, `pyperf` and the pyperformance CLI hit loader/stdlib blockers. Running these tools on CPython to control native executables remains useful. |

The earlier 146/473 stub sweep is a different inventory and revision; subtracting
those totals would create a false regression claim. This audit keeps the input
inventory, exclusions, environment, compiler hash and per-module results together.

## How much adaptation?

Here, *minor* means a localized annotation, import adjustment or API restriction
that retains the algorithm. *Major* means implementing a runtime/module hub or
changing the package's object model, data representation or supported API. These
are assessments of the measured workloads, not promises about the whole package.

| Level | Examples | Practical boundary |
|---|---|---|
| Works within shipped coverage | Bisect, colorsys, path-string helpers; selected regex, textwrap, collections, itertools, datetime, bytes and BytesIO operations | Read each module's supported input types and semantics. Module availability is not API completeness. |
| No package-source edits for a measured call | Upstream `sgp4.functions.jday`; six runner-replaced pyperformance sources | The call/benchmark driver still selects a concrete supported workload. |
| Minor adaptation | Fully annotate a cached function; annotate a recursive list return; bytes-only `base64` predicate adjustment; move a deferred local import to module scope | Fresh controls demonstrate local fixes for these exact calls. Other paths may still fail. |
| Existing maintained port | Roman, iniconfig, tomli-w, ordered-set, pylev, wcwidth, pyaes, qrcode, sortedcontainers and the other shipped ports | Adaptation burden varies; some are narrow API subsets or fixed element types. Package-specific limits are in the report and `PORT.md`. |
| Major compatibility work | Dynamic frameworks and general test runners; NumPy/pandas/pydantic runtime dependencies; full CPython extension loading; arbitrary recursive JSON-like values; general reflection/async execution | Fixing the first missing import is insufficient. Native extensions need an interoperability strategy; Python wrappers also need their semantics. |

Do not remove all annotations mechanically: the fresh `@lru_cache` example needs
both its argument and return annotated. Do not remove port edits solely because
their old comment says a feature was missing: prove the upstream form with its
actual workload first. [#521](https://github.com/den-run-ai/pystachy/issues/521)
and [#530](https://github.com/den-run-ai/pystachy/issues/530) own this cleanup.

## Correctness and usability gaps

The small probes and exact outcomes are retained in
[`compatibility-2026-10-17-gaps.json`](compatibility-2026-10-17-gaps.json), including
source text. Every rejection was checked with both the hosted and native compiler;
controls that compile were executed in JIT and AOT against CPython.

| Finding | Fresh result | Priority / owner |
|---|---|---|
| Unicode offsets differ silently | `len("café"), re.search("é", "café").span()` gives `5 (3, 5)` in JIT/AOT, versus CPython `4 (3, 4)` | High-impact semantic boundary for text packages; existing [#120](https://github.com/den-run-ai/pystachy/issues/120). `PYSTACHY_UNICODE_AUDIT=1` is a porting aid, not code-point semantics. |
| Integer width | `2 ** 63` emits IR but raises `OverflowError` in both modes; CPython returns `9223372036854775808` | Documented fixed-width limit; major for arbitrary-precision arithmetic/crypto workloads. Compilation alone misses it. |
| Forwarding mutual recursion regressed | The empty-list `a → b → a` case is rejected; adding `-> list[int]` to `a` matches CPython in both modes | Existing regression [#595](https://github.com/den-run-ai/pystachy/issues/595), with a small user workaround. |
| Numeric unions lack common consumers | `sum(xs)` for `xs: list[int | float]` is rejected; a homogeneous float list works | [#596](https://github.com/den-run-ai/pystachy/issues/596). A float-only conversion changes the API contract; it is not a universal replacement. |
| Cached templates need concrete signatures | Unannotated `square` fails; `square(x: int) -> int` gives `9 9` in both modes | [#620](https://github.com/den-run-ai/pystachy/issues/620). |
| Bare container annotations | `def size(xs: list)` fails | [#597](https://github.com/den-run-ai/pystachy/issues/597); use a concrete item type or supported inference. |
| Any signatures at this revision | `twice(x: Any) -> Any` fails | Open [#607](https://github.com/den-run-ai/pystachy/pull/607) plus [#616](https://github.com/den-run-ai/pystachy/issues/616)'s stack address selected inference positions. This is not arbitrary dynamic storage. |

These checks did not discover a new compiler crash or memory-corruption failure.
The Unicode mismatch and integer-width limit are documented semantics, not newly
introduced regressions. The tested inference regression is already tracked.

Two test/measurement gaps were reconfirmed: SciMark's zero-filled SOR/sparse
fixtures still pass after replacing the kernels with no-ops, and
`unpack_sequence` permits dead-work removal that invalidates its AOT speed ratio.
The [benchmark report](compatibility-2026-10-17-benchmarks.md) preserves the evidence
and links the existing #530 follow-up. Also, `encodings.utf_16` passes import and
IR generation but raises the documented `NotImplementedError` during execution.

## Blockers worth prioritizing

1. **Import-time language and stdlib hubs:** the actual sweep ranks `_weakref`,
   `_imp`, `_ast` and namedtuple among first blockers. The stub experiment shows
   how little a stand-in alone proves. Follow
   [#491](https://github.com/den-run-ai/pystachy/issues/491),
   [#610](https://github.com/den-run-ai/pystachy/issues/610) (enum),
   [#611](https://github.com/den-run-ai/pystachy/issues/611) (conditional defs), and
   [#612](https://github.com/den-run-ai/pystachy/issues/612) (module-level `del`).
2. **Small inference gaps with real callers:** cached functions (#620), recursive
   forwarding (#595), bare containers (#597), and the pending Any stack. These
   reduce hand edits without adding a general boxed runtime.
3. **Semantic coverage:** Unicode (#120), numeric-union consumers (#596), dynamic
   values/reflection and the supported APIs of each module. Broader import counts
   should not displace API-level checks.
4. **Performance and retained memory:** fresh measurements are separated into
   compile cost, JIT wall time, AOT launch and timed body in the benchmark report.
   Existing [#625](https://github.com/den-run-ai/pystachy/issues/625) tracks quadratic
   subclass-comparison dispatch growth; [#615](https://github.com/den-run-ai/pystachy/issues/615)
   tracks GC peak amplification. Their published large-scale numbers are not
   remeasurements from this audit. String/regex follow-ups
   [#627](https://github.com/den-run-ai/pystachy/issues/627) and
   [#628](https://github.com/den-run-ai/pystachy/issues/628) also remain relevant.

## Tooling corrections and reproducibility

- `tools/import_sweep.py --metadata PATH` now writes a separate provenance and
  counts file while preserving the existing module-result JSON. It records the
  compiler file hash and selected source-tree revision separately; neither is
  falsely presented as proof of the other. CLI validation and tests cover
  malformed inputs, conflicting outputs and legacy overlay forms.
- The pyperformance census now records `compile_status` separately from `ported`
  and reports a successful unported workload as "runner-only compiles; not
  ported". It previously printed "blocked" beside "none: compiles" for generators.
- `tools/census.py` remains a historical source heuristic. It flags constructs
  that now work, so it is not used for this report's compatibility numerator.
- `docs/stdlib.md` no longer claims all generator functions/objects are missing.
  `difflib.get_grouped_opcodes()` is distinguished from its remaining diff APIs.

Commands, package pins, source hashes, fixture programs and normalized results
are linked from the three detailed reports. Run with the CPython version in
`.python-version`, a complete LLVM toolchain and a newly built compiler. Timing
results on this shared machine are advisory; there is no wall-clock speed gate.

## Concurrent PRs

Subsequent checks and merge-driven remeasurements are recorded in the
[rolling findings log](compatibility-updates.md). The measurements above retain
their original source revision.

The main snapshot includes **#598 BytesIO, #599 singleton rebinding and #603
pointer-free numeric list storage**. Other sessions' branches were monitored
without modifying their work. At the final state check, the compatibility changes
in #600–#602, #604–#609, #622–#624 and #629–#634, plus #583, were still open; none of their
unmerged behavior is counted above. In particular, namedtuple, TextIOWrapper,
token, sys.warnoptions and Any improvements belong in the next remeasurement
after their respective merges. The detailed reports identify affected probes.
