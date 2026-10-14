# Type feedback for ordinary Python: a census, and the adaptive prototype

**Historical report.** Measured on 14 October 2026 against `main` at `aad4f1c` and
[PR #374](https://github.com/den-run-ai/pystachy/pull/374) at `ea8a617`, with the one-line fix of
§2.3, on a 4-core x86-64 VM (Intel Xeon, 2.1 GHz) with CPython 3.13.16, LLVM 18.1.3 and Numba 0.68.0.
Its counts and timings describe that revision and corpus, not later compilers.

PR #374 prototyped guarded native specialization of unannotated numeric functions. It followed a
suggestion to make Pystachy useful for Python without annotations with the techniques of Self:
polymorphic inline caches ([Hölzle, Chambers and Ungar, 1991](https://bibliography.selflanguage.org/pics.html)),
type feedback ([Hölzle's thesis](https://bibliography.selflanguage.org/urs-thesis.html)),
customization and splitting ([Chambers' thesis](https://bibliography.selflanguage.org/craig-thesis.html))
and selective specialization ([Dean, Chambers and Grove, PLDI 1995](https://dl.acm.org/doi/10.1145/223428.207119)).
The suggestion began with a cheap experiment: record the dynamic types of objects at call sites, see
whether their distribution is skewed, and whether specializing higher up the call stack removes what
is not. This report runs that experiment over 52 ordinary Python programs (§1), and measures the
prototype against the same code compiled without runtime type discovery (§2).

## Summary

- **The types are very skewed, and context removes most of the rest.** Over 52 workloads and
  47 million calls into program code:
  - in the median workload, every call is at an inline-cache site with one target and receiver class
    (mean 90%), and 97% on average are at sites with at most four, which a polymorphic inline cache
    holds. The exceptions dispatch on purpose: richards' tasks, deltablue's constraints, docutils'
    visitors, sympy's expression nodes, sqlglot's expressions and html5lib's tokenizer states.
  - 78% of calls on average go to a function that needs one Pystachy specialization. Counted per
    function and caller's argument types, which is cloning the caller, 93% do; the gain is 48 to 69
    points in docutils, sympy, sqlglot, deltablue, snowballstemmer, pylev, chameleon and the regex
    compiler.
- **What blocks Pystachy is what the types are, not finding them.** Weighted by time, the median
  workload spends 76% of its program-code time in calls whose argument types Pystachy can express
  (mean 62%). The first inexpressible type of a call is, by share of calls: inheritance 27%, a
  generator or iterator 7%, bytes 2%, a class object 2%, an integer beyond 64 bits 1.5%; containers
  of mixed types are rare (0.2%). The int, float, bool and str arguments of the ext ABI cover 5% of
  the median workload's time.
- **The prototype is careful, but its subset runs almost nothing in the corpus, and its dispatch
  costs more than a small function.**
  - Its native variants matched CPython in about 35,000 differential cases (§2.4).
  - On its demo kernel it runs at AOT speed: within 4% of its generated extension called directly,
    and of `pystachy build` of the same unannotated function, which static templates specialize
    without a profile. The 40-50x over CPython is AOT's, not type feedback's.
  - Its Python guards cost about 1.6 us per call, 16-36x a small function's CPython call. The only
    function of the corpus that it accepts and that matters, spectral_norm's `eval_A` (37% of that
    benchmark's time), makes the benchmark 13x slower. The same extension called without the guards
    makes it 2.6x faster.
  - Kernels with a float literal are disabled when imported, and the first signatures seen keep the
    variant slots (§2.3).
- **Where this points (§3):** profiles as specialization input to the static compiler; for a
  CPython-hosted mode, compiled regions with guards in C at their entry; and the language features
  that the census ranks: inheritance first.

## 1. Call-site type census

### 1.1 Method

`tools/typeprofile.py record` runs a program under `sys.monitoring` (PEP 669) and counts each Python
function entry by its call site (the caller's code and instruction offset), the function entered and
its arguments' types. A *class* is the type a polymorphic inline cache keys on. A *deep type* also
samples up to three items of a container (`list[int]`, `dict[str:list[int]]`, `tuple[int,str]`),
the form a template specialization needs. Two contexts are kept per call: the caller's own call site
(a call string of depth 2) and the caller's deep argument types. Return types are counted per
function and argument types; instance fields are sampled when `__init__` returns and at one method
entry in 16. A separate `time` run under cProfile weights each call by its function's own time per
call. The recorder never runs program code: it reads frames, `type()`, raw instance dictionaries and
container items by iteration.

The report views:

| View | Key | An entry |
|---|---|---|
| Inline cache | call site | the target, with its receiver's class for a method (`self` or `cls`) |
| Function entry | function | the arguments' classes |
| Pystachy specializations | function, alone or with its call site, call string or caller's types | a group of deep signatures that one specialization can share |

Deep signatures join as Pystachy's typing does (docs/language/typing.md): `None` joins any type
(`T | None`), an empty container takes its item type from context, and `None` items make optional
items. `int`, `bool` and `float` stay distinct, since there is no implicit conversion. A deep type is
*expressible* when the typing reference gives it a Pystachy type: a 64-bit `int`, `float`, `bool`,
`str`, homogeneous containers with supported keys, tuples of at most nine items, classes without
inheritance (exceptions and NamedTuples may inherit), functions as values, and the library classes
with Pystachy implementations (`re`, `io.StringIO`, files, `difflib`, `textwrap`, `string`, `csv`).

*Program code* excludes the standard library, which Pystachy ships separately; workloads with fewer
than 1,000 program calls are left out of the tables, since their work is in C, the standard library
or one loop. Limitations: each program runs once, with its import-time code; sampling three items can
miss a mixed container; cProfile inflates the own time of small functions; methods are recognized by
the name of their first parameter.

**Positive control.** Pystachy's CPython-hosted compiler, which is written in the subset, compiling
`tests/algorithms.py`: 88,330 calls, 100% on every view, every call's arguments expressible, every
field keeping one type, and 99.99% of returns fixed by their arguments' types.

### 1.2 Corpus

- **pyperformance** 1.14.0: 49 of its benchmark scripts in 56 runs (five scripts run once for each
  workload their manifest names), each once, in-process, through a stand-in for pyperf. They include
  the applications it pins: docutils, html5lib, genshi, sqlglot, networkx, chameleon, sympy and
  tomli. Left out: services and networking, subprocess and startup timers, the collector benchmarks,
  sqlite, and the applications not installed for this run (django, dask, sqlalchemy, sphinx, mako,
  tornado, fastapi, dulwich, yaml, xdsl, coverage). 35 runs make at least 1,000 calls into program
  code.
- **Upstream ports:** the unmodified PyPI releases of the libraries under `ports/`, running the ports'
  differential workloads (`tests/port_*.py`). A workload counts only if its output matches the CPython
  output recorded in `tests/`: 26 of 30 do (pyaes, sgp4's two and wcwidth's core differ upstream),
  and 17 make at least 1,000 program calls.

### 1.3 Skew

| | workloads | calls | inline cache: one target and receiver class | ... at most 4 (a PIC) | function entry: one class tuple | one Pystachy specialization per function | ... per call site | ... per call string of 2 | ... per caller's types |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 1 | 88,330 | 100% (100%) | 100% (100%) | 100% (100%) | 100% (100%) | 100% (100%) | 100% (100%) | 100% (100%) |
| pyperformance | 35 | 45,714,234 | 100% (22%) | 100% (52%) | 85% (5.8%) | 81% (14%) | 100% (20%) | 100% (20%) | 100% (20%) |
| upstream ports | 17 | 1,249,247 | 100% (87%) | 100% (88%) | 99% (24%) | 100% (37%) | 100% (39%) | 100% (41%) | 100% (93%) |

Median (minimum) over workloads, each weighted equally.

| workload | | calls | inline cache: one target and receiver class | ... at most 4 (a PIC) | function entry: one class tuple | one Pystachy specialization per function | ... per call site | ... per call string of 2 | ... per caller's types |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| control_compiler | control | 88,330 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_async_generators | pyperformance | 400,017 | 100% | 100% | 75% | 100% | 100% | 100% | 100% |
| bm_bpe_tokeniser | pyperformance | 1,821,829 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_chameleon | pyperformance | 57,251 | 98% | 99% | 33% | 33% | 99% | 99% | 99% |
| bm_chaos | pyperformance | 270,966 | 100% | 100% | 63% | 63% | 100% | 100% | 100% |
| bm_coroutines | pyperformance | 242,799 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_crypto_pyaes | pyperformance | 20,178 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_deltablue | pyperformance | 51,454 | 59% | 100% | 36% | 36% | 83% | 86% | 95% |
| bm_docutils | pyperformance | 5,116,227 | 39% | 52% | 32% | 32% | 42% | 47% | 79% |
| bm_float | pyperformance | 300,015 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_generators | pyperformance | 400,057 | 100% | 100% | 75% | 100% | 100% | 100% | 100% |
| bm_genshi | pyperformance | 211,949 | 90% | 90% | 84% | 72% | 73% | 73% | 73% |
| bm_go | pyperformance | 920,504 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_hexiom | pyperformance | 45,434 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_html5lib | pyperformance | 179,790 | 67% | 72% | 85% | 88% | 95% | 97% | 97% |
| bm_mdp | pyperformance | 1,680,720 | 100% | 100% | 100% | 52% | 67% | 67% | 67% |
| bm_meteor_contest | pyperformance | 31,697 | 100% | 100% | 100% | 99% | 99% | 99% | 99% |
| bm_nqueens | pyperformance | 82,769 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_pidigits | pyperformance | 32,557 | 100% | 100% | 100% | 20% | 20% | 20% | 20% |
| bm_pyflate | pyperformance | 1,599,751 | 100% | 100% | 100% | 94% | 100% | 100% | 100% |
| bm_raytrace | pyperformance | 2,867,095 | 92% | 100% | 78% | 77% | 83% | 92% | 88% |
| bm_regex_compile | pyperformance | 4,475 | 100% | 100% | 31% | 31% | 100% | 100% | 100% |
| bm_richards | pyperformance | 481,332 | 22% | 100% | 6.6% | 22% | 36% | 46% | 62% |
| bm_richards_super | pyperformance | 547,122 | 32% | 100% | 5.8% | 20% | 44% | 52% | 66% |
| bm_scimark | pyperformance | 2,370,602 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_spectral_norm | pyperformance | 681,274 | 99% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_sympy | pyperformance | 3,022,198 | 50% | 63% | 32% | 28% | 40% | 45% | 80% |
| bm_tomli_loads | pyperformance | 5,506,874 | 100% | 100% | 100% | 81% | 81% | 81% | 93% |
| bm_async_tree_none | pyperformance | 102,672 | 45% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_networkx_shortest_path | pyperformance | 4,946,131 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_networkx_connected_components | pyperformance | 4,946,147 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| bm_networkx_k_core | pyperformance | 6,011,915 | 100% | 100% | 79% | 79% | 100% | 100% | 100% |
| bm_sqlglot_v2_parse | pyperformance | 10,052 | 88% | 94% | 84% | 76% | 89% | 91% | 93% |
| bm_sqlglot_v2_transpile | pyperformance | 11,025 | 87% | 93% | 79% | 72% | 87% | 91% | 92% |
| bm_sqlglot_v2_optimize | pyperformance | 218,075 | 72% | 81% | 16% | 16% | 31% | 36% | 70% |
| bm_sqlglot_v2_normalize | pyperformance | 521,281 | 65% | 91% | 14% | 14% | 30% | 41% | 64% |
| port_convertdate_calendars | upstream ports | 610,501 | 100% | 100% | 98% | 99% | 100% | 100% | 100% |
| port_convertdate_holidays | upstream ports | 38,318 | 100% | 100% | 91% | 99% | 100% | 100% | 100% |
| port_jdcal_convert | upstream ports | 54,314 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| port_ordered_set_api | upstream ports | 8,137 | 87% | 100% | 95% | 92% | 98% | 98% | 99% |
| port_ordered_set_edges | upstream ports | 18,260 | 99% | 100% | 100% | 100% | 100% | 100% | 100% |
| port_pyfiglet_edges | upstream ports | 53,196 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| port_pyfiglet_render | upstream ports | 30,583 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| port_pylev_sequences | upstream ports | 1,308 | 100% | 100% | 38% | 37% | 39% | 41% | 100% |
| port_pylev_strings | upstream ports | 11,557 | 100% | 100% | 24% | 100% | 100% | 100% | 100% |
| port_qrcode_encode | upstream ports | 231,773 | 88% | 88% | 99% | 99% | 100% | 100% | 100% |
| port_roman_convert | upstream ports | 15,139 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| port_roman_validate | upstream ports | 2,865 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| port_snowballstemmer_stem | upstream ports | 76,572 | 90% | 100% | 27% | 38% | 92% | 99% | 100% |
| port_sortedcontainers_index | upstream ports | 8,275 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| port_sqids_blocklist | upstream ports | 5,536 | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| port_sqids_encode | upstream ports | 2,510 | 100% | 100% | 95% | 95% | 95% | 100% | 95% |
| port_tomli_w_tables | upstream ports | 80,403 | 100% | 100% | 88% | 83% | 84% | 85% | 93% |

Polymorphic sites, from the report of each recording:

| Workload | Inline cache: one / 2-4 / more entries | The busiest polymorphic site |
|---|---|---|
| richards | 22% / 78% / 0% | `schedule`: `isTaskHoldingOrWaiting` and `runTask` on 4 task classes |
| deltablue | 59% / 41% / 0% | `Plan.execute`: 3 constraint classes, 82% one of them |
| docutils | 39% / 13% / 48% | `Node._fast_findall` on 93 node classes |
| sympy | 50% / 13% / 37% | the `cacheit` wrapper: `__hash__` of about 200 classes |
| sqlglot optimize | 72% / 9% / 19% | `_norm_args`: 28 expression classes |
| html5lib | 67% / 4% / 28% | the tokenizer's state method: 30 targets |
| raytrace | 92% / 8% / 0% | `Point.__sub__`: vectors from integer literals, `Vector(0, 1, 0)`, among float ones |

### 1.4 What Pystachy would need

| | workloads | calls | time in program Python code | one specialization per caller's types (time) | arguments have Pystachy types (time) | returns fixed by argument types | fields keep one type | arguments fit the ext ABI (time) | adaptive prototype could run natively (time) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 1 | 88,330 | 66% (66%) | 100% (100%) | 100% (100%) | 100% (100%) | 100% (100%) | 6.0% (6.0%) | 0% (0%) |
| pyperformance | 35 | 45,714,234 | 58% (1.8%) | 100% (1.0%) | 61% (0%) | 100% (43%) | 100% (12%) | 3.1% (0%) | 0% (0%) |
| upstream ports | 17 | 1,249,247 | 51% (30%) | 100% (94%) | 99% (10%) | 100% (99%) | 100% (80%) | 31% (0%) | 0% (0%) |

Median (minimum) over workloads, each weighted equally.

| workload | | calls | time in program Python code | one specialization per caller's types (time) | arguments have Pystachy types (time) | returns fixed by argument types | fields keep one type | arguments fit the ext ABI (time) | adaptive prototype could run natively (time) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| control_compiler | control | 88,330 | 66% | 100% | 100% | 100% | 100% | 6.0% | 0% |
| bm_async_generators | pyperformance | 400,017 | 28% | 100% | 26% | 100% | 100% | 9.8% | 0% |
| bm_bpe_tokeniser | pyperformance | 1,821,829 | 71% | 100% | 97% | 100% | 100% | 97% | 0% |
| bm_chameleon | pyperformance | 57,251 | 12% | 99% | 13% | 43% | 80% | 3.5% | 0% |
| bm_chaos | pyperformance | 270,966 | 66% | 100% | 100% | 100% | 69% | 0% | 0% |
| bm_coroutines | pyperformance | 242,799 | 57% | 100% | 100% | 100% | 100% | 100% | 0% |
| bm_crypto_pyaes | pyperformance | 20,178 | 52% | 100% | 94% | 100% | 100% | 0% | 0% |
| bm_deltablue | pyperformance | 51,454 | 24% | 97% | 18% | 99% | 98% | 3.1% | 0% |
| bm_docutils | pyperformance | 5,116,227 | 72% | 80% | 5.8% | 93% | 86% | 2.9% | 0% |
| bm_float | pyperformance | 300,015 | 70% | 100% | 100% | 100% | 100% | 31% | 0% |
| bm_generators | pyperformance | 400,057 | 36% | 100% | 22% | 100% | 100% | 5.8% | 0% |
| bm_genshi | pyperformance | 211,949 | 19% | 84% | 19% | 57% | 98% | 12% | 0% |
| bm_go | pyperformance | 920,504 | 83% | 100% | 100% | 93% | 100% | 0% | 0% |
| bm_hexiom | pyperformance | 45,434 | 23% | 100% | 99% | 100% | 100% | 0.6% | 0% |
| bm_html5lib | pyperformance | 179,790 | 46% | 97% | 42% | 99% | 88% | 2.7% | 0% |
| bm_mdp | pyperformance | 1,680,720 | 35% | 90% | 79% | 99% | 67% | 1.2% | 0% |
| bm_meteor_contest | pyperformance | 31,697 | 60% | 100% | 100% | 100% | 100% | 0% | 0% |
| bm_nqueens | pyperformance | 82,769 | 3.0% | 100% | 11% | 100% | 100% | 11% | 0% |
| bm_pidigits | pyperformance | 32,557 | 71% | 1.0% | 1.3% | 100% | 100% | 1.0% | 0% |
| bm_pyflate | pyperformance | 1,599,751 | 81% | 100% | 0% | 100% | 100% | 0% | 0% |
| bm_raytrace | pyperformance | 2,867,095 | 93% | 91% | 97% | 81% | 12% | 0% | 0% |
| bm_regex_compile | pyperformance | 4,475 | 1.8% | 100% | 98% | 100% | 100% | 60% | 0% |
| bm_richards | pyperformance | 481,332 | 75% | 67% | 22% | 73% | 91% | 20% | 0% |
| bm_richards_super | pyperformance | 547,122 | 80% | 71% | 19% | 76% | 92% | 17% | 0% |
| bm_scimark | pyperformance | 2,370,602 | 86% | 100% | 32% | 100% | 100% | 3.8% | 0% |
| bm_spectral_norm | pyperformance | 681,274 | 81% | 100% | 100% | 100% | 100% | 46% | 37% |
| bm_sympy | pyperformance | 3,022,198 | 64% | 71% | 5.0% | 78% | 99% | 2.2% | 0% |
| bm_tomli_loads | pyperformance | 5,506,874 | 87% | 82% | 61% | 76% | 100% | 34% | 0% |
| bm_async_tree_none | pyperformance | 102,672 | 5.3% | 100% | 0% | 100% | 100% | 0% | 0% |
| bm_networkx_shortest_path | pyperformance | 4,946,131 | 58% | 100% | 72% | 100% | 75% | 0% | 0% |
| bm_networkx_connected_components | pyperformance | 4,946,147 | 63% | 100% | 74% | 100% | 75% | 0% | 0% |
| bm_networkx_k_core | pyperformance | 6,011,915 | 67% | 100% | 79% | 100% | 52% | 0% | 0% |
| bm_sqlglot_v2_parse | pyperformance | 10,052 | 7.8% | 96% | 67% | 90% | 100% | 20% | 0% |
| bm_sqlglot_v2_transpile | pyperformance | 11,025 | 9.6% | 95% | 63% | 91% | 100% | 17% | 0% |
| bm_sqlglot_v2_optimize | pyperformance | 218,075 | 44% | 78% | 9.5% | 95% | 93% | 3.2% | 0% |
| bm_sqlglot_v2_normalize | pyperformance | 521,281 | 48% | 75% | 4.2% | 95% | 100% | 1.8% | 0% |
| port_convertdate_calendars | upstream ports | 610,501 | 75% | 100% | 100% | 100% | 100% | 99% | 1.8% |
| port_convertdate_holidays | upstream ports | 38,318 | 51% | 100% | 100% | 100% | 100% | 98% | 0% |
| port_jdcal_convert | upstream ports | 54,314 | 73% | 100% | 100% | 100% | – | 100% | 0% |
| port_ordered_set_api | upstream ports | 8,137 | 32% | 96% | 18% | 100% | 100% | 18% | 0% |
| port_ordered_set_edges | upstream ports | 18,260 | 43% | 100% | 34% | 100% | 100% | 34% | 0% |
| port_pyfiglet_edges | upstream ports | 53,196 | 38% | 100% | 99% | 100% | 100% | 0.6% | 0% |
| port_pyfiglet_render | upstream ports | 30,583 | 35% | 100% | 99% | 100% | 100% | 0% | 0% |
| port_pylev_sequences | upstream ports | 1,308 | 30% | 100% | 100% | 100% | – | 3.8% | 0% |
| port_pylev_strings | upstream ports | 11,557 | 60% | 100% | 100% | 100% | – | 31% | 0% |
| port_qrcode_encode | upstream ports | 231,773 | 71% | 100% | 99% | 99% | 100% | 11% | 0% |
| port_roman_convert | upstream ports | 15,139 | 57% | 100% | 100% | 100% | – | 100% | 0% |
| port_roman_validate | upstream ports | 2,865 | 38% | 100% | 100% | 100% | – | 100% | 0% |
| port_snowballstemmer_stem | upstream ports | 76,572 | 70% | 100% | 10% | 100% | 100% | 9.5% | 0% |
| port_sortedcontainers_index | upstream ports | 8,275 | 38% | 100% | 31% | 100% | 100% | 31% | 0% |
| port_sqids_blocklist | upstream ports | 5,536 | 50% | 100% | 97% | 100% | 80% | 4.3% | 0% |
| port_sqids_encode | upstream ports | 2,510 | 58% | 100% | 99% | 100% | 80% | 1.5% | 0% |
| port_tomli_w_tables | upstream ports | 80,403 | 52% | 94% | 96% | 100% | 100% | 85% | 0% |

Each call's first inexpressible argument type, as a mean share of calls over the 52 workloads:
inheritance 27.1%, a generator or iterator 6.6%, bytes 2.0%, a class object 1.7% (tomli's
`parse_float=float`), an integer beyond 64 bits 1.5% (pidigits), another library class 0.9%, an
enum 0.5%, a container of mixed types 0.2%. Fields that change type are rarer, but decide raytrace
(12% of field samples keep one type: vectors mix integer components with float ones) and chaos (69%).

Fewer than 1,000 calls into program code, left out: bm_base64 (34), bm_comprehensions (106), bm_deepcopy (27), bm_fannkuch (14), bm_json_dumps (16), bm_json_loads (17), bm_logging (22), bm_nbody (20), bm_pathlib (16), bm_pprint (14), bm_regex_dna (22), bm_regex_effbot (192), bm_regex_v8 (26), bm_telco (16), bm_typing_runtime_protocols (37), bm_unpack_sequence (19), bm_xml_etree (65), bm_argparse_many_optionals (16), bm_argparse_subparsers (18), bm_pickle_pure_python_pickle (21), bm_pickle_pure_python_unpickle (21), port_convertdate_star (542), port_iniconfig_api (508), port_iniconfig_parse (311), port_jdcal_extremes (414), port_pylev_imports (734), port_sortedcontainers_api (845), port_tomli_w_ini2toml (198), port_tomli_w_values (389), port_wcwidth_edges (67)

Skipped: port_pyaes_cipher (output differs from the recorded CPython output); port_sgp4_api (output differs from the recorded CPython output); port_sgp4_verify (output differs from the recorded CPython output); port_wcwidth_core (output differs from the recorded CPython output)

## 2. The adaptive prototype

### 2.1 Without runtime type discovery

`tools/adaptive_eval.py PR_CHECKOUT` measures the PR's demo kernel, `weighted_sum(x, n)` with 200,000
iterations, in each mode. Times exclude compilation; the in-process modes run in interleaved rounds,
pinned to one CPU:

| mode | int,int | float,int |
|---|---:|---:|
| CPython | 7,775.8 us (1.00x) | 8,019.1 us (1.00x) |
| adaptive wrapper | 198.2 us (39.24x) | 160.0 us (50.13x) |
| ext, called directly | 191.5 us (40.60x) | 155.7 us (51.52x) |
| numba.njit | 155.7 us (49.94x) | 174.6 us (45.93x) |
| Pystachy JIT, annotated | 392.0 us (19.83x) | 505.5 us (15.86x) |
| Pystachy AOT, annotated | 193.4 us (40.20x) | 164.2 us (48.85x) |
| Pystachy JIT, unannotated | 386.5 us (20.12x) | 497.2 us (16.13x) |
| Pystachy AOT, unannotated | 192.0 us (40.50x) | 173.0 us (46.36x) |

Median time per call, and speed relative to CPython.

The wrapper is within 4% of its own extension called directly, and both match AOT. The unannotated
programs are templates, which the compiler specializes from their call sites with no profile. The
JIT's gap is consistent with docs/internals.md: it does not inline the precompiled runtime, which AOT
links and optimizes with the program. Numba, whose `jit` also compiles one version per observed
argument types, is faster on the integer kernel, whose arithmetic it does not check for overflow,
and slower on the float one. Building a variant took 0.44-0.6 s, of which the frontend and IR take
3 ms: the rest is LLVM's optimization and the link with the runtime, so the CPython-hosted compiler
(0.47 s) is no slower than the native one.

### 2.2 Small functions

| mode | eval_A(int, int) | add(int, int) |
|---|---:|---:|
| CPython | 100.0 ns (1.00x) | 46.0 ns (1.00x) |
| adaptive wrapper | 1,604.0 ns (0.06x) | 1,641.0 ns (0.03x) |
| ext, called directly | 45.0 ns (2.22x) | 45.0 ns (1.02x) |
| numba.njit | 137.0 ns (0.73x) | 149.0 ns (0.31x) |

Time per call, and speed relative to CPython.

The wrapper's checks run in Python on every call: the thread, tracing and profiling hooks, the
`range` binding, a tuple of exact types and value ranges. That costs about 1.6 us, while a direct
call of the extension costs less than CPython's own call. spectral_norm calls `eval_A` 676,000 times
per iteration:

| mode | one iteration |
|---|---:|
| CPython | 81.8 ms (1.00x) |
| adaptive wrapper | 1,087.7 ms (0.08x) |
| ext, called directly | 31.1 ms (2.63x) |
| numba.njit | 96.1 ms (0.85x) |

The difference is the dispatch: about 1.5 us in the wrapper's Python, and 90-100 ns more than a
direct call in Numba's C dispatcher, which is still slower than CPython's own call here. Elsewhere in
the corpus the subset accepts functions with at most 1.8% of a workload's time (convertdate).

### 2.3 Defects

1. **Float literals disable kernels on every import path.** `_source` compares constants with
   `marshal.dumps(actual.co_consts) != marshal.dumps(expected.co_consts)`. Marshal sets `FLAG_REF`
   on an object whose reference count is above one, so equal float constants can serialize
   differently (`g` against `0xe7`). The kernel is then disabled with "source does not match the
   function's constants" when its module is imported fresh, from a cached `.pyc`, or run by `runpy`.
   It works only as the `__main__` script, which is how the demo and the native test run it.
   `marshal.dumps(..., 2)` writes no references and still tells `1`, `1.0`, `True`, `0.0` and
   `-0.0` apart; the PR's 19 tests pass with it.
2. **The first signatures keep the slots.** `_profiles` admits the first `max_variants` signatures
   ever seen and never counts others. With `max_variants=2`, two signatures called three times at
   startup took both slots, and a third called 20 times afterwards never compiled: 0 native calls,
   149 ms where native code takes 4. Counting all signatures in a bounded table and compiling by
   count would follow the profile.

### 2.4 Differential checks

Native variants against CPython on random and edge inputs, including results' exact types and the
bits of floats: true division, floor division and modulo of 64-bit integers near the limits and of
floats (`1.0 // 0.1`, signed zeros, tiny and huge operands), mixed `int` and `float`, `range` with a
zero step, and a read of a variable a zero-trip loop never assigned. 0 mismatches in 35,051 cases.
Overflow replays the Python function as documented, at the cost of at most one native run on top of
CPython's.

## 3. Implications

- **For the static compiler**, the profile is most useful as input to specialization. Within a
  caller's specialization, a call site's types are fixed in 93% of calls on average, which is what
  template specialization relies on; a census row also gives the deep types of parameters, returns
  and fields where inference stops, the cheapest piece that
  [#264](https://github.com/den-run-ai/pystachy/issues/264) left open ("traced types, applied only
  where a compile error asks for an annotation").
- **For a CPython-hosted mode**, compile regions rather than leaves: the profile supplies a root's
  argument types, the existing templates specialize its callees, which is customization done at
  compile time, and the guard runs once at the root, in C. That needs containers and objects across
  the boundary (the ext ABI covers 5% of the median workload's time) and, for most of this corpus,
  inheritance and generators.
- **Inline caches with deoptimization** are the techniques in their full form, and the census shows
  they would pay. They need a representation for any value and a way back to it from specialized
  code, which a static AOT compiler does not have; CPython's specializing interpreter (PEP 659) and
  PyPy provide them for CPython's semantics.

## 4. Reproducing

```sh
python3 -m venv build/census-venv
build/census-venv/bin/pip install -r tools/typeprofile-requirements.txt
build/census-venv/bin/python tools/typeprofile_corpus.py build/census --python build/census-venv/bin/python \
    --eligibility PR_CHECKOUT/tools/adaptive.py
python3 -m unittest discover -s tools -p test_typeprofile.py
build/census-venv/bin/pip install numba==0.68.0
taskset -c 3 build/census-venv/bin/python tools/adaptive_eval.py PR_CHECKOUT
```

`PR_CHECKOUT` is a checkout of PR #374 with its compiler built; without the fix of §2.3,
`adaptive_eval.py` stops at `eval_A`, which the prototype disables when imported. The corpus run takes
about 5 minutes on 4 cores and writes each recording, its timing and `summary.json` to `build/census`.
`typeprofile.py report` prints every view of a recording, with its most polymorphic sites.
