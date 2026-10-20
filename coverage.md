## Hosted compiler coverage

Commit `8990e41776e8e74f57812120f81ec3e897065eda`: statements **95.9%** (31944 of 33312) and branches **92.6%** (16890 of 18240); 94.7% together, coverage.py's total. 5 suites, 5243 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5007 passed, 0 failed | 5015 | 2282 s | 94.6% | 91.0% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 136 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 125 | 79 s | 40.0% | 31.8% |
| cache | `tests/cache.sh` | 67 passed, 0 failed | 33 | 138 s | 31.6% | 22.1% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 85 tests, OK | 2 | 7 s | 50.3% | 42.4% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 68 programs | 68 | 61 s | 58.5% | 50.6% |
| **all** | | | **5243** | | **95.9%** | **92.6%** |

The other suites run 420 statements and 295 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1399 | 76 | 94.6% | 1200 | 86 | 92.8% | 93.8% | 93.7% |
| `src/pystachy_compiler/builtins.py` | 2160 | 100 | 95.4% | 1276 | 96 | 92.5% | 94.3% | 94.1% |
| `src/pystachy_compiler/calls.py` | 1114 | 49 | 95.6% | 690 | 46 | 93.3% | 94.7% | 92.1% |
| `src/pystachy_compiler/containers.py` | 751 | 31 | 95.9% | 410 | 32 | 92.2% | 94.6% | 94.6% |
| `src/pystachy_compiler/conversions.py` | 251 | 8 | 96.8% | 150 | 6 | 96.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/declarations.py` | 2251 | 136 | 94.0% | 1512 | 129 | 91.5% | 93.0% | 92.2% |
| `src/pystachy_compiler/diagnostics.py` | 31 | 0 | 100.0% | 8 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 553 | 72 | 87.0% | 224 | 44 | 80.4% | 85.1% | 69.0% |
| `src/pystachy_compiler/emission.py` | 437 | 19 | 95.7% | 138 | 11 | 92.0% | 94.8% | 94.4% |
| `src/pystachy_compiler/exceptions.py` | 1146 | 32 | 97.2% | 542 | 28 | 94.8% | 96.4% | 96.4% |
| `src/pystachy_compiler/expressions.py` | 3204 | 92 | 97.1% | 1898 | 95 | 95.0% | 96.3% | 96.3% |
| `src/pystachy_compiler/flow.py` | 766 | 6 | 99.2% | 534 | 10 | 98.1% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 280 | 7 | 97.5% | 160 | 5 | 96.9% | 97.3% | 76.6% |
| `src/pystachy_compiler/gen.py` | 1998 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 920 | 39 | 95.8% | 370 | 44 | 88.1% | 93.6% | 93.6% |
| `src/pystachy_compiler/ir.py` | 318 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 340 | 25 | 92.6% | 282 | 25 | 91.1% | 92.0% | 77.5% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2388 | 71 | 97.0% | 1472 | 77 | 94.8% | 96.2% | 95.9% |
| `src/pystachy_compiler/local_versions.py` | 35 | 0 | 100.0% | 24 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 321 | 4 | 98.8% | 162 | 3 | 98.1% | 98.6% | 49.3% |
| `src/pystachy_compiler/lowering.py` | 390 | 3 | 99.2% | 234 | 4 | 98.3% | 98.9% | 98.7% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 29 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 544 | 10 | 98.2% | 334 | 16 | 95.2% | 97.0% | 96.2% |
| `src/pystachy_compiler/parser.py` | 1999 | 103 | 94.8% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 924 | 34 | 96.3% | 676 | 32 | 95.3% | 95.9% | 94.9% |
| `src/pystachy_compiler/reflection.py` | 1889 | 137 | 92.7% | 1002 | 136 | 86.4% | 90.6% | 90.4% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 234 | 0 | 100.0% | 80 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1576 | 61 | 96.1% | 856 | 64 | 92.5% | 94.9% | 94.7% |
| `src/pystachy_compiler/structs.py` | 224 | 27 | 87.9% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 145 | 4 | 97.2% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 715 | 39 | 94.5% | 432 | 47 | 89.1% | 92.5% | 92.5% |
| `src/pystachy_compiler/union_arithmetic.py` | 115 | 3 | 97.4% | 50 | 3 | 94.0% | 96.4% | 96.4% |
| `src/pystachy_compiler/unions.py` | 412 | 27 | 93.4% | 216 | 25 | 88.4% | 91.7% | 91.7% |
| `src/pystachy_compiler/utils.py` | 567 | 26 | 95.4% | 280 | 24 | 91.4% | 94.1% | 93.3% |
| `src/pystachy_compiler/variables.py` | 1612 | 95 | 94.1% | 986 | 100 | 89.9% | 92.5% | 92.5% |
