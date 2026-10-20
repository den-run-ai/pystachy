## Hosted compiler coverage

Commit `ad19255e448be45ac098443936798755053139d7`: statements **95.7%** (33184 of 34679) and branches **92.3%** (17468 of 18916); 94.5% together, coverage.py's total. 5 suites, 5329 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5093 passed, 0 failed | 5101 | 2291 s | 94.5% | 90.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 136 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 125 | 128 s | 39.2% | 30.9% |
| cache | `tests/cache.sh` | 67 passed, 0 failed | 33 | 174 s | 31.1% | 21.5% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 85 tests, OK | 2 | 11 s | 49.2% | 41.3% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 68 programs | 68 | 114 s | 57.1% | 49.2% |
| **all** | | | **5329** | | **95.7%** | **92.3%** |

The other suites run 420 statements and 295 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1399 | 76 | 94.6% | 1200 | 86 | 92.8% | 93.8% | 93.7% |
| `src/pystachy_compiler/builtins.py` | 2173 | 100 | 95.4% | 1288 | 96 | 92.5% | 94.3% | 94.1% |
| `src/pystachy_compiler/calls.py` | 1118 | 49 | 95.6% | 694 | 46 | 93.4% | 94.8% | 92.1% |
| `src/pystachy_compiler/containers.py` | 755 | 30 | 96.0% | 414 | 31 | 92.5% | 94.8% | 94.8% |
| `src/pystachy_compiler/conversions.py` | 257 | 8 | 96.9% | 156 | 6 | 96.2% | 96.6% | 96.6% |
| `src/pystachy_compiler/declarations.py` | 2258 | 135 | 94.0% | 1518 | 128 | 91.6% | 93.0% | 92.3% |
| `src/pystachy_compiler/diagnostics.py` | 46 | 0 | 100.0% | 14 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 553 | 72 | 87.0% | 224 | 44 | 80.4% | 85.1% | 69.0% |
| `src/pystachy_compiler/dynamic.py` | 980 | 115 | 88.3% | 500 | 85 | 83.0% | 86.5% | 86.5% |
| `src/pystachy_compiler/emission.py` | 441 | 19 | 95.7% | 140 | 11 | 92.1% | 94.8% | 94.5% |
| `src/pystachy_compiler/exceptions.py` | 1146 | 32 | 97.2% | 542 | 28 | 94.8% | 96.4% | 96.4% |
| `src/pystachy_compiler/expressions.py` | 3242 | 96 | 97.0% | 1934 | 99 | 94.9% | 96.2% | 96.2% |
| `src/pystachy_compiler/flow.py` | 766 | 6 | 99.2% | 534 | 10 | 98.1% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 295 | 9 | 96.9% | 166 | 7 | 95.8% | 96.5% | 76.8% |
| `src/pystachy_compiler/gen.py` | 2165 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 921 | 39 | 95.8% | 370 | 44 | 88.1% | 93.6% | 93.6% |
| `src/pystachy_compiler/ir.py` | 321 | 0 | 100.0% | 18 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 347 | 27 | 92.2% | 290 | 27 | 90.7% | 91.5% | 77.4% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2392 | 72 | 97.0% | 1476 | 78 | 94.7% | 96.1% | 95.9% |
| `src/pystachy_compiler/local_versions.py` | 38 | 0 | 100.0% | 26 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 336 | 4 | 98.8% | 170 | 3 | 98.2% | 98.6% | 51.6% |
| `src/pystachy_compiler/lowering.py` | 392 | 3 | 99.2% | 236 | 4 | 98.3% | 98.9% | 98.7% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 29 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 547 | 10 | 98.2% | 336 | 16 | 95.2% | 97.1% | 96.3% |
| `src/pystachy_compiler/parser.py` | 1999 | 103 | 94.8% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 929 | 34 | 96.3% | 680 | 32 | 95.3% | 95.9% | 94.9% |
| `src/pystachy_compiler/reflection.py` | 1891 | 137 | 92.8% | 1004 | 136 | 86.5% | 90.6% | 90.4% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 238 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1603 | 63 | 96.1% | 880 | 67 | 92.4% | 94.8% | 94.6% |
| `src/pystachy_compiler/structs.py` | 224 | 27 | 87.9% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 145 | 4 | 97.2% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 717 | 39 | 94.6% | 434 | 47 | 89.2% | 92.5% | 92.5% |
| `src/pystachy_compiler/union_arithmetic.py` | 115 | 3 | 97.4% | 50 | 3 | 94.0% | 96.4% | 96.4% |
| `src/pystachy_compiler/unions.py` | 416 | 28 | 93.3% | 220 | 26 | 88.2% | 91.5% | 91.5% |
| `src/pystachy_compiler/utils.py` | 569 | 27 | 95.3% | 282 | 25 | 91.1% | 93.9% | 93.1% |
| `src/pystachy_compiler/variables.py` | 1642 | 96 | 94.2% | 1012 | 101 | 90.0% | 92.6% | 92.5% |
