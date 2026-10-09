# History and design decisions

Pystachy started on 7 October 2026 as a renamed copy of the Ouro v1 compiler and grew
through a short series of pull requests. This page keeps the decisions that shaped it: what
was decided, why, and where it happened. Individual bug fixes are left out; the pull
requests list them.

## Timeline

| when | milestone | PR |
|---|---|---|
| 7–8 Oct 2026 | Ouro v1 imported as Pystachy, then v0.0.1: the collector, checked ints, definite assignment, timsort, CPython's dict layout, `make verify` and CI | [#1](https://github.com/den-run-ai/pystachy/pull/1) |
| 8–9 Oct | Python modules and packages; unannotated functions compiled as templates | [#2](https://github.com/den-run-ai/pystachy/pull/2) |
| 8–9 Oct | Standard-library modules that compile unmodified (`lib/`), and the evaluation report [stdlib.md](stdlib.md) | [#3](https://github.com/den-run-ai/pystachy/pull/3) |
| 8 Oct | Review of #1–#3 (correctness, scalability, interoperability) and the roadmap M0–M7 | issues [#4](https://github.com/den-run-ai/pystachy/issues/4), [#5](https://github.com/den-run-ai/pystachy/issues/5) |
| 9 Oct | M0 correctness: CPython's syntax errors, the loader's import-time semantics, inference gaps, nesting limits | [#18](https://github.com/den-run-ai/pystachy/pull/18) |
| 9 Oct | Linear-time compilation, and a dict hash without clustering | [#20](https://github.com/den-run-ai/pystachy/pull/20) |
| 9 Oct | Typed-IR design, the IR-identity oracle (`make irsame`) and `make check-ir` | [#21](https://github.com/den-run-ai/pystachy/pull/21) |
| in progress | The typed IR itself (steps 4–8, byte-identical), optional types, the first IR optimizations; exceptions being merged | [#22](https://github.com/den-run-ai/pystachy/pull/22) (draft) |
| in progress | Part of the runtime written in the subset (`runtime.py`) | [#19](https://github.com/den-run-ai/pystachy/pull/19) (draft) |

#2, #3, #18, #20 and #21 were a stack, each based on the one before, and were merged in that
order on 9 October.

## Decisions

Each row says what was decided, why, and where to read more.

### Ground rules

| decision | why | where |
|---|---|---|
| Start from Ouro v1 | Of the four self-hosting subset compilers compared, it had the broadest subset, matched CPython most closely, compiled in linear time, ran fastest and was the cheapest to extend. | [below](#where-it-comes-from), [#1](https://github.com/den-run-ai/pystachy/pull/1) |
| The compiler compiles itself, to a byte-identical fixed point | CPython runs the same source, so any divergence between Pystachy and CPython inside the compiler shows up as a diff. | [internals.md](internals.md#bootstrap), [#1](https://github.com/den-run-ai/pystachy/pull/1) |
| CPython's output is the contract | Programs are ordinary Python files, so CPython rather than a written spec decides what is correct: every test must print what CPython prints, JIT and AOT. | [testing.md](testing.md#differential-tests), [#1](https://github.com/den-run-ai/pystachy/pull/1) |
| Reject rather than miscompile | A clear `file:line: error:` is better than a program that silently behaves differently, so where matching CPython would take a large feature, the program is rejected. | [language.md](language.md#rejected-rather-than-miscompiled), [#1](https://github.com/den-run-ai/pystachy/pull/1), [#18](https://github.com/den-run-ai/pystachy/pull/18) |
| Leave dynamic features out on purpose, and add them back by measured payoff | Exceptions, generators, closures, inheritance, sets, `bytes` and big ints each need a dynamic runtime or a large compiler feature, and the roadmap measures what each would let compile before adding it back (milestones M1–M7). | [language.md](language.md#removed-on-purpose), [stdlib.md](stdlib.md#6-what-it-would-take-to-compile-more), [#5](https://github.com/den-run-ai/pystachy/issues/5) |

### Values and the runtime

| decision | why | where |
|---|---|---|
| 64-bit ints, overflow-checked | Ouro v1 wrapped silently and big ints are left out on purpose, so overflow raises `OverflowError` (MiniPy's choice), which costs most on call-heavy code (`fib` 0.05 s instead of 0.024 s). | [language.md](language.md#deviations-from-cpython), [performance.md](performance.md), [#1](https://github.com/den-run-ai/pystachy/pull/1) |
| `str` holds UTF-8 bytes | Kept from Ouro v1: ASCII behaves exactly as in CPython and other text passes through unchanged, while format widths, `repr()` and `ord()` count characters. | [language.md](language.md#deviations-from-cpython), [#1](https://github.com/den-run-ai/pystachy/pull/1) |
| A conservative mark-and-sweep collector with no dependencies | Ouro v1 never freed memory; the collector keeps peak memory near the live set (50 MiB instead of 1.5 GiB for fifty discarded 2M-element lists) and needs only the C library. | [internals.md](internals.md#memory), [#1](https://github.com/den-run-ai/pystachy/pull/1) |
| A port of CPython 3.13's timsort | It makes the same comparisons in the same order, which decides where NaNs end up and what an `__lt__` with side effects sees, and it beat the earlier merge sort (0.32 s instead of 0.53 s for 2M ints). | [internals.md](internals.md#python-semantics-in-the-runtime), [#1](https://github.com/den-run-ai/pystachy/pull/1) |
| CPython 3.13's compact dict layout and probe order, over a one-multiply hash | The layout makes deletion O(1) and a loop that changes its dict fail exactly as in CPython, and the probe order with SplitMix64 mixing stopped keys like `i << 46` from clustering, for about 2 ns more per lookup in tables larger than the cache. | [internals.md](internals.md#python-semantics-in-the-runtime), [#1](https://github.com/den-run-ai/pystachy/pull/1), [#20](https://github.com/den-run-ai/pystachy/pull/20) |

### Modules and the standard library

| decision | why | where |
|---|---|---|
| Unannotated functions are templates | 82% of the standard library's functions have unannotated parameters, so such a function is compiled once per list of argument types, only when a call needs it. | [language.md](language.md#typing-rules), [internals.md](internals.md#templates), [#2](https://github.com/den-run-ai/pystachy/pull/2) |
| Decide at compile time what CPython decides at import time | To compile standard-library modules, the loader decides their `__main__` guards, `TYPE_CHECKING` blocks, platform tests (for POSIX) and optional C-accelerator imports, keeping side effects and respecting names that shadow them (#18). | [language.md](language.md#decided-at-compile-time-as-cpython-decides-it-at-import-time), [#2](https://github.com/den-run-ai/pystachy/pull/2), [#18](https://github.com/den-run-ai/pystachy/pull/18) |
| The definition-time rule for imported modules | Unused functions stay uncompiled, but each `def` and `class` statement still runs where CPython runs it, with its annotations and the defaults Pystachy can compile evaluated there, and what stays uncompiled (decorators, bases, class bodies) must run no program code, so laziness cannot change what an import does. | [language.md](language.md#code-pystachy-cannot-compile-in-an-imported-module), [#4](https://github.com/den-run-ai/pystachy/issues/4) §1, [#2](https://github.com/den-run-ai/pystachy/pull/2), [#18](https://github.com/den-run-ai/pystachy/pull/18) |
| Vendor only modules that compile unmodified | Byte-for-byte copies with SHA-256s, each with a differential test, show what compiles as it is; the 17 modules that need small edits are listed in the report instead. | [language.md](language.md#the-vendored-standard-library), [stdlib.md](stdlib.md), [#3](https://github.com/den-run-ai/pystachy/pull/3) |
| Report CPython's syntax errors exactly | Lazy compilation let syntax errors in never-compiled code through ([#15](https://github.com/den-run-ai/pystachy/issues/15)), so every `SyntaxError` CPython reports before running a file is now a compile-time error with its message and line, compared with `compile()` on 5,701 files. | [language.md](language.md#syntax-errors), [testing.md](testing.md#syntax-errors-against-cpython), [#18](https://github.com/den-run-ai/pystachy/pull/18) |

### The compiler

| decision | why | where |
|---|---|---|
| Linear-time compilation, checked in CI | The review found an O(F × G) pass (#4 §2), so `make verify` now counts what the hosted compiler executes on generated programs and fails if that grows faster than the program, with no timing threshold. | [testing.md](testing.md#make-verify), [performance.md](performance.md), [#4](https://github.com/den-run-ai/pystachy/issues/4) §2, [#20](https://github.com/den-run-ai/pystachy/pull/20) |
| One pass from AST to IR, now becoming a typed IR | Ouro v1's single walk types and emits at once, so a type cannot be computed without emitting code and optimizations or a second backend have nowhere to live; the typed IR keeps the walk but makes it build typed instructions that a separate pass lowers to LLVM. | [internals.md](internals.md#one-pass-from-ast-to-ir), [typed-ir.md](typed-ir.md), [#21](https://github.com/den-run-ai/pystachy/pull/21) |
| Lowering first, proven byte for byte | Of three designs written independently, both judges chose lowering first because only it had working evidence (a prototype at the fixed point, 358 of 358 programs identical), and `make irsame` requires every migration step to leave the whole corpus's IR byte-identical. | [typed-ir.md](typed-ir.md#appendix-a-how-this-design-was-chosen), [testing.md](testing.md#ir-identity-for-refactors), [#21](https://github.com/den-run-ai/pystachy/pull/21) |

### In progress and open

| decision | why | where |
|---|---|---|
| Exceptions through table-driven unwinding (in progress) | v0.0.1 planned LLVM landing pads and typed-ir.md §7.2 then proposed an error flag; the draft #22 answers that open question with measurements, using `invoke`/`landingpad` with Pystachy's own personality routine, and programs without `try` keep their IR byte for byte. | [typed-ir.md](typed-ir.md) §7.2 and §9, [#22](https://github.com/den-run-ai/pystachy/pull/22) |
| Part of the runtime in the subset (in progress) | Runtime code can then be Python, tested on CPython itself, and a WebAssembly GC backend needs such a runtime; functions move one at a time into `runtime.py` with no program's IR changing, while the collector, memory layouts, files and signals stay in C. | [#19](https://github.com/den-run-ai/pystachy/pull/19) |
| Standalone mode, or also a CPython-extension mode (open, nothing decided) | Broad package support needs an interoperability strategy as well as features: #5 estimates that even with every feature, standalone mode makes only 288 of 821 pure-Python top packages at least half usable, and #4 §4 recommends evaluating an AOT extension mode in which CPython keeps imports, dynamic objects and dependencies. | [#4](https://github.com/den-run-ai/pystachy/issues/4) §4, [#5](https://github.com/den-run-ai/pystachy/issues/5), [typed-ir.md](typed-ir.md) §7.4 |

## Where it comes from

Pystachy is built on the design of **Ouro v1** (*ouroboros*), one of four self-hosting
Python-subset compilers that were compared before this repository was started: Ouro v1
(LLVM), Ouro v2 (WebAssembly GC) and two MiniPy compilers (C). None of them is published,
so the comparison and the Ouro v1 numbers quoted in [performance.md](performance.md) cannot
be reproduced from this repository. Ouro v1 had the broadest subset, matched CPython's
output most closely, compiled in linear time, ran fastest and was the cheapest to extend (a
builtin is one table line plus one C function). The reviews also named its weaknesses, and
Pystachy addresses them:

| review finding about Ouro v1 | Pystachy |
|---|---|
| memory is never freed | a conservative mark-and-sweep collector in `runtime.c`, no dependencies |
| ints wrap silently on overflow | checked arithmetic: `OverflowError` (MiniPy's choice) |
| a variable set on one branch reads as 0 | a definite-assignment pass; reads that may fail raise `UnboundLocalError`/`NameError` |
| mutable default arguments are recreated per call | defaults are evaluated once, when `def` runs |
| a zero `range` step loops silently | `ValueError` |
| attribute access through `None` is undefined behaviour | `AttributeError`, CPython's `None` rules for `==`, `str()` |
| unknown imports are silently ignored | imports are checked; aliases and `from` imports work |
| driver writes fixed `/tmp` files via `os.system` | a private `mkdtemp` directory, removed on every exit path but a `SIGTERM` to the driver |
| type checking and emission are one class with no IR | still true: a typed IR is in progress ([typed-ir.md](typed-ir.md)) |

Ouro v2 contributed 16 test programs (ported as `tests/ouro2_*.py`) and the idea of a second
backend; MiniPy contributed checked arithmetic, strict definite assignment and its
verification discipline: sanitizer builds, a Python-free native stage and a
machine-readable report. Four rounds of adversarial differential testing against CPython
followed (the language core; numbers and strings; containers, files and errors; then a
review of the result as a whole); every divergence they found is now fixed, rejected at
compile time, or listed under [*Deviations from CPython*](language.md#deviations-from-cpython).
