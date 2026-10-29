# Promoting integer identity: correctness and integration evidence

The promoting-int/`Any` identity failure is repaired by extending the existing numeric
companion scheme. The completed native oracle finds no new rejection. Focused execution,
GC and bootstrap checks pass on the final identity source. The final identity, runtime and
combined PR heads passed their complete CI matrices and were merged. Release publication
still requires successful workflows on the exact versioned main commit.

## Evaluated sources

The local and published commit identities differ because publication preserved the remote
branch histories. Equal tree IDs below establish identical tracked source contents; they
do not substitute for checking the source and inputs of each test run.

| Role | Local source | Published source | Tree |
|---|---|---|---|
| Baseline main | `5b49dcfaf639d943a12cbc00ce9117ba3e7b5fcc` | Same | `b98d3faaebab3d57c98a0179b4fc439061522be6` |
| Final identity fix and fixtures | `26cae9ed59d7a64cd0f26e358d35ab92b65c477c` | [#981, `ac28b3cf`](https://github.com/den-run-ai/pystachy/commit/ac28b3cf4880cb69774e7900d4681c44261aa21f) | `bbdae6c42634bf5dc82f47be5dad24197c2b7d53` |
| Identity fix plus module scoping, before runtime fast path | `be12e700f3f4714923b3172b2b10fae740976f95` | Isolated local comparison | `ac6f6c046f840d64fd645c022020bc996b370efe` |
| Runtime/identity integration | `e9e36cb9eebd5bc1e92afbb285a365caf79a79ce` | [#980, `d58a7915`](https://github.com/den-run-ai/pystachy/commit/d58a791581fedce4d6d8ca66924c9e639e8392a3) | `6f9ebf7b7b7e6fd47f44a33043b7ff8e8140904e` |
| Combined identity, module scoping and runtime fast path | `eb11dab661be2fc04147761edb95c3376493bb43` | [#973, `9fd73f34`](https://github.com/den-run-ai/pystachy/commit/9fd73f34a36cfae6196f165628b2ed19fa16538b) | `c996c5698c3b201d959cde9e3fc9fff3313cc549` |

Checks use pinned CPython **3.13.16** and LLVM/Clang **18.1.3** on Linux x86-64.
Differential expectations were recorded with that CPython, including the recovered wide-value
fixture. The native oracle uses executables built from identity `0ad6467c` and scoped `28093c5a`.
Their final fixture heads `26cae9ed` and `be12e700` have no production-source differences;
recorded binary hashes verify reuse. These are native comparisons, not hosted compilation.

## Repaired behavior and retained boundaries

A promoting integer now carries the same binding identity through copies, parameters,
returns, fields, optional values, indirect calls, closures and defaults. Fitting values use
an identity box; values outside signed int64 have a null companion. Creating or preserving
that companion never narrows the typed value or raises overflow. Actual conversion into
`Any` still checks the existing int64 boundary. The field regression therefore distinguishes
successful wide typed stores from `OverflowError` when the field is read through `Any`.

The regressions also cover independent equal values, literal constants, field/local chained
assignments, list-item transfers, narrowed shared optional cells, generic captures across
module policies, and two-word captured defaults. These cover the alias and layout failures
independently of #973's original two fixtures. Proven-int arithmetic retains a promoting
accumulator when `isinstance(value, int)` proves an `Any` operand is an int or bool; operand
order and bool bitwise result types are checked. Both obsolete TOML rejection entries were
removed from the strict promoting-int gate, with no new exception added.

This does not enable both opt-ins in one module, make `Any` hold arbitrary-size integers,
or establish complete identity support for every tuple, dict, set or generator boundary.

## Execution and structural verification

| Source | Verification | Result |
|---|---|---|
| Final identity `0ad6467c` | Numeric-identity and promoting-int gate unit suites | 56 + 43 = **99 passed** |
| Final identity `0ad6467c` | Arithmetic/TOML follow-up: ordinary normal/GC and promoting normal forms, JIT/AOT | **24 hosted + 24 native checks passed**; each total includes six repeated normal promoting checks, not promoting-GC checks |
| Final identity `0ad6467c` | Three-stage compiler and subset-runtime bootstrap | Fixed points: **767,057 / 18,805 IR lines** |
| Final identity `0ad6467c` | Program IR and runtime contracts | **2,075 programs** accepted by the IR checker and `llvm-as`; **579 runtime entries / 70 exception classes** agree |
| Scoped source `28093c5a` | Three-stage compiler and subset-runtime bootstrap | Fixed points: **769,688 / 18,805 IR lines** |
| Final identity `26cae9ed`, production sources unchanged from `0ad6467c` | Explicit promoting overlay, native JIT/AOT, per-allocation GC | **34/34 checks passed** across 17 cases |
| Final scoped source `be12e700`, production sources unchanged from `28093c5a` | Same explicit promoting overlay, native JIT/AOT, per-allocation GC | **34/34 checks passed** across 17 cases |

The preceding identity-only source `1a906130` passed **26 genuinely GC-stressed native checks**
over 13 ordinary-entry/deviation cases, plus **24 normal promoting-overlay checks** over
12 cases. Those are earlier-source results, not a full rerun on the arithmetic/TOML follow-up.
For final source `0ad6467c`, each 24-check frontend total comprises six ordinary normal checks,
six ordinary per-allocation-GC checks, six promoting normal checks and six repeated promoting
normal checks. They are focused execution evidence, not a complete compatibility gate or
`make verify`.

The unit suites are `test_numeric_identity.py` and `test_python_int*.py`, run with
`python -m unittest discover -s tools -p PATTERN`. The final execution set consists of
`dynany_promote_arithmetic.py`, `dynany_promote_arithmetic_wide.py` and `lib_tomllib.py`:
`tests/run.sh` checks each frontend in JIT/AOT, and `tools/python_int_optin.py` checks the
promoted variants. The direct harness honors `PYSTACHY_GC_STRESS_PROGRAM=1`; the opt-in tool
resets it to zero in its child environment. Consequently, the runs previously labelled
promoted-GC were additional normal runs. The separately verified direct-overlay run below
supplies that missing evidence; the earlier runs are not retrospectively relabelled.

The direct-overlay run uses clean fixture source `26cae9ed59d7a64cd0f26e358d35ab92b65c477c`,
tree `bbdae6c42634bf5dc82f47be5dad24197c2b7d53`. Its compiler, library and runtime production
sources are unchanged from `0ad6467c`; the native compiler SHA-256 is
`3ee76c34f819ed4aec51e464ecd304f0b5fb17e05688bbce38c261791e708458`, matching the identity
oracle. A fresh overlay applies `python-int` to 12 identity fixtures, two arithmetic fixtures,
TOML and the import/list fixtures. Each receives a fresh pinned-CPython recording. After the
standard environment sanitization, the run explicitly sets `PYSTACHY_GC_STRESS_PROGRAM=1`
and invokes `tests/run.sh` directly in both modes: **34 passed, zero failed**. The direct
harness passes the interval to program execution; it does not use the resetting opt-in runner.
The checkout remained clean at the same head before and after execution. The scoped
`be12e700` checkout separately passed the same **34/34 genuine GC checks**, using compiler
SHA-256 `67d36c70a5b9ede6a7e0b78228cfe3e387c5ba05591aaed7808e696d72f99999`.

That fixture follow-up separates wide typed-list consumption from the existing `Any` boundary
deviation without changing production code. Its three affected cases pass six native normal
checks and six native GC checks. The strict dynamic-Any gate passes the import case in both
modes; the dedicated already-promoting list case retains its exact dual-opt-in rejection
(two expected failures, zero unexpected failures). Both obsolete import-case exceptions were
removed. The final native oracles below were rerun on these updated fixture inventories.

## Native compiler comparisons

The final identity comparison covers **3,861 inputs** against baseline main: **3,851 are
byte-identical** in IR, diagnostic bytes and exit status. All ten differences are classified:

| Cases | Classification |
|---|---|
| Chained module and field fixtures | One identity snapshot is shared by the assignment targets. |
| Wide storage fixture and existing promoting numeric-protocol fixture | Companion storage/ABI and guarded boxing changes; typed values remain intact. |
| Existing generic-library, roots and varargs fixtures | Captured cells/default environments reserve sufficient space for promoting integers. |
| Wide proven-int arithmetic fixture | Newly accepted; typed arithmetic replaces the old attempted conversion into `Any`. |
| Wide-`Any`-field deviation | Newly accepted with the documented runtime int64 check at the read, rather than premature rejection. |
| Wide-`Any`-list deviation | Fitting promoting items are accepted; wide values still raise `OverflowError` only on the actual dynamic-list crossing. Typed factorial computation remains wide. |

There are **seven IR-only changes, three new acceptances, and no new rejections, crashes or
timeouts**. Baseline accepted 2,073 inputs; candidate accepted 2,076. Complete library/runtime
input manifests were compared before using a shared source home. No textual or path
normalization was applied. Source inputs and compiler executables remained unchanged across
the run.

The separate scoping comparison uses final fixture heads `26cae9ed` versus `be12e700`,
isolating #973 from the runtime-only optimization. It completed **3,865 inputs: 3,861
byte-identical and four IR-only
differences**, with no changed diagnostics, exit statuses, acceptances, rejections, crashes or
timeouts. Its library/runtime manifests match, and source/compiler inputs remained stable.
All four differences are classified. The scope differential fixture and IR guard remove the
typed Counter's two companion fields, local bookkeeping and two read-boxing calls. The TOML
fixture removes companion globals/roots and two boxing calls for its entry module's scalar
success/error counters. The wide-arithmetic fixture removes unobserved accumulator companions
and generation counters without changing its arithmetic/runtime call multiset. Imported
dynamic operations and the whole-program function ABI remain; other differences are explained
symbol, block or SSA renumbering. Both compilers accept 2,080 inputs in this expanded corpus.

## Merged-source CI and release gate

Each final PR head passed all 34 CI jobs, plus Installation, Packages, Lint and Performance
smoke; the same-repository DCO check was an expected skip. The merged trees match the
validated source trees listed above.

| Change | Merge commit | Final PR CI |
|---|---|---|
| Identity fix, #981 | [`9b50a385`](https://github.com/den-run-ai/pystachy/commit/9b50a3851ed66c792c07f4c7cbaabd6af04b6d8e) | [40806960611](https://github.com/den-run-ai/pystachy/actions/runs/40806960611) |
| Runtime fast path, #980 | [`5252b842`](https://github.com/den-run-ai/pystachy/commit/5252b842788d2958f5c4e5d6220b8816149e53e9) | [40807581778](https://github.com/den-run-ai/pystachy/actions/runs/40807581778) |
| Combined module scoping, #973 | [`770fe20f`](https://github.com/den-run-ai/pystachy/commit/770fe20ff7c50771b140a918b06843402a456cfa) | [40807585377](https://github.com/den-run-ai/pystachy/actions/runs/40807585377) |

The runtime hashing/probe-order checks and the Counter/JSON acceptance measurements are
recorded separately in the [combined performance report](release-blocker-performance-2026-10-29.md).
These results support release preparation, with the measured JSON residual retained. They
do not claim the unavailable historical numeric workload was recovered or fulfilled.

At this documentation checkpoint, post-merge main workflows are still running. PR checks
and earlier main checks are not substitutes for CI, Installation, Lint and Packages on the
exact versioned release candidate. The [release tracker](https://github.com/den-run-ai/pystachy/issues/976)
records that final gate. No alpha.4 tag or release is created by this preparation change.

The [immutable research evidence directory](https://github.com/den-run-ai/pystachy/tree/717ae5852f30a4f70cf5ba36cda359fbf99d36cf/research/release-blocker-2026-10-29)
contains `verification-final.tar.gz` (2,048,930 bytes, SHA-256
`0e10ef8c7beb4f08b6a9bd742794c10986e2feb027b9e107005943a4582c655a`).
It retains the exact final oracle summaries, classifications, case inventories, input
manifests and per-case result hashes; all 14 changed-case text diffs; both genuine-GC
reports and logs; scripts and source/binary provenance. Thousands of raw LLVM outputs and
native binaries are intentionally excluded. Their recorded SHA-256 values remain available
for reproduction; the archive is evidence, not a replacement for CI.
