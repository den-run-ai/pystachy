# History and design decisions

Pystachy began on 7 October 2026 from the Ouro v1 compiler. This page records the early
milestones and decisions that shaped it. It is a historical record; the [language guide](language.md),
[library reference](../lib/README.md) and [internals](internals.md) describe the current implementation.

## Timeline

| Date | Early milestone | Record |
|---|---|---|
| 7–8 Oct 2026 | Ouro v1 imported; checked integers, garbage collection, definite assignment, timsort, compact dictionaries and verification established. | [#1](https://github.com/den-run-ai/pystachy/pull/1) |
| 8–9 Oct | Python modules/packages and unannotated function templates. | [#2](https://github.com/den-run-ai/pystachy/pull/2) |
| 8–9 Oct | Initial unchanged standard-library sources and coverage survey. | [#3](https://github.com/den-run-ai/pystachy/pull/3), [archived survey](archive/stdlib-survey.md) |
| 8 Oct | Correctness, scalability and interoperability review; initial roadmap. | [#4](https://github.com/den-run-ai/pystachy/issues/4), [#5](https://github.com/den-run-ai/pystachy/issues/5) |
| 9 Oct | Syntax checks, import-time semantics, inference gaps and nesting limits addressed. | [#18](https://github.com/den-run-ai/pystachy/pull/18) |
| 9 Oct | Compiler scaling checks and improved dictionary hashing. | [#20](https://github.com/den-run-ai/pystachy/pull/20) |
| 9 Oct | Typed-IR design and the IR-identity oracle. | [#21](https://github.com/den-run-ai/pystachy/pull/21) |
| 9 Oct | Initial typed IR, optional values, NamedTuples, tuple dictionary keys, IR optimizations, exception unwinding and the iniconfig port. | [#22](https://github.com/den-run-ai/pystachy/pull/22) |
| 9 Oct | First runtime functions moved into the typed subset. | [#19](https://github.com/den-run-ai/pystachy/pull/19) |

The module/IR work was a stack: #2, #3, #18, #20 and #21 merged in that order; #19 followed
#22. Later work expanded class templates, callables, closures, sets, generic cache wrappers and
library ports. Their current behavior is documented in the guides above; individual fixes
and measurements remain in the repository's pull requests.

## Decisions

<a id="ground-rules"></a>

### Language and verification

| Decision | Reason and current reference |
|---|---|
| Keep programs valid Python. | CPython provides an executable reference for supported behavior. [Differential testing](testing.md#differential-tests) compares JIT and AOT results, with explicit deviations kept separately. |
| Compile the compiler to a fixed point. | Successive self-compiled stages must reproduce the compiler and subset runtime's IR byte for byte. See [bootstrap](internals.md#bootstrap). |
| Reject unsupported behavior with a source diagnostic. | Silent miscompilation violates the compatibility contract. The [compatibility reference](language/compatibility.md) separates rejected programs from intentional deviations. |
| Add features through useful applications and measured payoff. | The initial roadmap used library surveys to rank work. Many of its proposed features have since shipped; its percentages are historical projections, not current coverage. See [library porting](stdlib.md). |

<a id="values-and-the-runtime"></a>

### Values and runtime

| Decision | Reason and current reference |
|---|---|
| Checked 64-bit integers. | Preserve a compact native representation and raise `OverflowError` rather than wrapping. Arbitrary precision remains outside the subset. See [types](language.md#types). |
| UTF-8 byte strings. | Retain the original runtime representation. Length/indexing and some Unicode operations differ from CPython; see [string compatibility](language/compatibility.md). |
| Conservative mark-and-sweep collection. | Replace Ouro v1's unreclaimed allocations while keeping the standalone runtime independent of CPython. See [memory](internals.md#memory). |
| CPython-derived sorting and dictionary algorithms. | Comparison order and mutation checks are observable behavior. Runtime probes also check dictionary hashing and storage bounds. See [runtime internals](internals.md) and [verification](testing.md#make-verify). |
| Move suitable runtime functions into the subset. | The same Python source can run under CPython for differential checks and compile to native runtime functions. Memory layouts, collection and platform facilities remain in C. See [runtime in the subset](runtime-in-subset.md). |

<a id="modules-and-the-standard-library"></a>

### Library reuse

The first library milestone vendored only unchanged CPython files. Subsequent ports established
three approaches: unchanged upstream code, adapted upstream code with marked edits, and
implementations written in the subset. The [library reference](../lib/README.md) records which
approach each module uses; the old “unchanged only” rule is no longer the coverage policy.

Unannotated functions specialize for call types, and unused unsupported APIs need not compile.
This makes library reuse practical, but import-time behavior still matters: definitions,
defaults, decorators and module effects must obey the supported
[module rules](language/modules.md). Syntax checks also apply to unused source.

<a id="the-compiler"></a>

### Compiler architecture

The original compiler combined typing and LLVM text emission in one walk. The typed-IR work
introduced instructions and blocks before LLVM lowering, giving JIT and AOT a shared place
for checks and optimization. The [IR reference](typed-ir.md) describes the implemented structure
and the remaining migration work.

Early refactors used [IR identity](testing.md#ir-identity-for-refactors) to prove they changed no
code generation. Compiler scaling is guarded by deterministic execution/operation counts.
Exceptions settled an earlier design question by using LLVM `invoke` / `landingpad` and a
runtime personality routine; the [internals guide](internals.md) explains that implementation.

<a id="open"></a>

### Interoperability

The initial review left standalone-only versus CPython integration open. C calls, AOT
CPython extension builds and calls from compiled code into an embedded CPython (`pyobj`) now
have an experimental implementation; use the [FFI guide](ffi.md) for implemented directions
and restrictions.

## Where it comes from

Ouro v1 was selected after internal comparisons with Ouro v2 (WebAssembly GC) and two MiniPy
compilers (C). Those prototypes are unpublished; their comparative performance claims cannot
be reproduced from this repository.

Pystachy retained Ouro v1's LLVM design and added checked arithmetic, definite-assignment checks,
correct default-argument lifetime, runtime error handling, import validation and garbage
collection. Ouro v2 contributed the `tests/ouro2_*.py` programs and the idea of a second backend.
MiniPy influenced checked arithmetic and the verification approach, including sanitizer builds,
a Python-free stage and machine-readable reports.

The archived [library survey](archive/stdlib-survey.md) and
[verification snapshots](archive/verification-snapshots.md) preserve early measurements.
Current claims should use fresh results and the current documented compatibility boundaries.
