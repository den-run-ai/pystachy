## Hosted compiler coverage

Commit `42fabd724e63bf7d4ef8c72335688894a8a90d54`: statements **95.9%** (34740 of 36232) and branches **92.5%** (18264 of 19736); 94.7% together, coverage.py's total. 5 suites, 5617 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5380 passed, 0 failed | 5388 | 2572 s | 94.7% | 91.0% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 139 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 126 | 129 s | 38.9% | 30.9% |
| cache | `tests/cache.sh` | 67 passed, 0 failed | 33 | 222 s | 30.5% | 21.0% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 95 tests, OK | 2 | 12 s | 49.7% | 41.8% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 68 programs | 68 | 121 s | 56.3% | 48.6% |
| **all** | | | **5617** | | **95.9%** | **92.5%** |

The other suites run 422 statements and 298 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1399 | 72 | 94.9% | 1200 | 83 | 93.1% | 94.0% | 94.0% |
| `src/pystachy_compiler/builtins.py` | 2218 | 100 | 95.5% | 1316 | 96 | 92.7% | 94.5% | 94.2% |
| `src/pystachy_compiler/calls.py` | 1211 | 52 | 95.7% | 750 | 52 | 93.1% | 94.7% | 92.2% |
| `src/pystachy_compiler/containers.py` | 767 | 31 | 96.0% | 424 | 33 | 92.2% | 94.6% | 94.6% |
| `src/pystachy_compiler/conversions.py` | 258 | 8 | 96.9% | 156 | 6 | 96.2% | 96.6% | 96.6% |
| `src/pystachy_compiler/declarations.py` | 2293 | 137 | 94.0% | 1546 | 127 | 91.8% | 93.1% | 92.4% |
| `src/pystachy_compiler/diagnostics.py` | 48 | 0 | 100.0% | 14 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 559 | 72 | 87.1% | 228 | 44 | 80.7% | 85.3% | 69.4% |
| `src/pystachy_compiler/dynamic.py` | 1402 | 87 | 93.8% | 692 | 78 | 88.7% | 92.1% | 92.1% |
| `src/pystachy_compiler/emission.py` | 484 | 19 | 96.1% | 146 | 11 | 92.5% | 95.2% | 94.9% |
| `src/pystachy_compiler/exceptions.py` | 1164 | 33 | 97.2% | 550 | 29 | 94.7% | 96.4% | 96.4% |
| `src/pystachy_compiler/expressions.py` | 3428 | 97 | 97.2% | 2042 | 101 | 95.1% | 96.4% | 96.4% |
| `src/pystachy_compiler/flow.py` | 766 | 6 | 99.2% | 534 | 10 | 98.1% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 311 | 9 | 97.1% | 168 | 7 | 95.8% | 96.7% | 77.7% |
| `src/pystachy_compiler/gen.py` | 2263 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 921 | 39 | 95.8% | 370 | 44 | 88.1% | 93.6% | 93.6% |
| `src/pystachy_compiler/ir.py` | 338 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 360 | 26 | 92.8% | 302 | 26 | 91.4% | 92.1% | 77.3% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2528 | 76 | 97.0% | 1560 | 83 | 94.7% | 96.1% | 95.9% |
| `src/pystachy_compiler/local_versions.py` | 38 | 0 | 100.0% | 26 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 349 | 4 | 98.9% | 180 | 3 | 98.3% | 98.7% | 53.7% |
| `src/pystachy_compiler/lowering.py` | 394 | 3 | 99.2% | 238 | 4 | 98.3% | 98.9% | 98.7% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 30 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 811 | 13 | 98.4% | 514 | 25 | 95.1% | 97.1% | 96.8% |
| `src/pystachy_compiler/parser.py` | 1999 | 103 | 94.8% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 934 | 34 | 96.4% | 684 | 32 | 95.3% | 95.9% | 94.9% |
| `src/pystachy_compiler/reflection.py` | 1926 | 149 | 92.3% | 1028 | 144 | 86.0% | 90.1% | 89.9% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 240 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1621 | 63 | 96.1% | 896 | 67 | 92.5% | 94.8% | 94.7% |
| `src/pystachy_compiler/structs.py` | 224 | 27 | 87.9% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 146 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 717 | 39 | 94.6% | 434 | 47 | 89.2% | 92.5% | 92.5% |
| `src/pystachy_compiler/union_arithmetic.py` | 115 | 3 | 97.4% | 50 | 3 | 94.0% | 96.4% | 96.4% |
| `src/pystachy_compiler/unions.py` | 416 | 29 | 93.0% | 220 | 27 | 87.7% | 91.2% | 91.2% |
| `src/pystachy_compiler/utils.py` | 573 | 25 | 95.6% | 282 | 23 | 91.8% | 94.4% | 93.6% |
| `src/pystachy_compiler/variables.py` | 1707 | 100 | 94.1% | 1062 | 105 | 90.1% | 92.6% | 92.6% |
