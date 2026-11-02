## Hosted compiler coverage

Commit `a62eaac20b5697027f547bca7fa4db1a1a059c70`: statements **96.0%** (41394 of 43123) and branches **92.5%** (21690 of 23438); 94.8% together, coverage.py's total. 5 suites, 6400 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 6142 passed, 0 failed | 6150 | 2999 s | 94.9% | 91.0% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 145 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 131 | 110 s | 37.1% | 28.7% |
| cache | `tests/cache.sh` | 68 passed, 0 failed | 34 | 194 s | 28.3% | 18.8% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 160 tests, OK | 2 | 9 s | 48.8% | 41.3% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 83 programs | 83 | 114 s | 57.6% | 50.8% |
| **all** | | | **6400** | | **96.0%** | **92.5%** |

The other suites run 475 statements and 351 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1578 | 72 | 95.4% | 1336 | 84 | 93.7% | 94.6% | 94.6% |
| `src/pystachy_compiler/bigints.py` | 969 | 38 | 96.1% | 400 | 42 | 89.5% | 94.2% | 94.2% |
| `src/pystachy_compiler/builtins.py` | 2441 | 113 | 95.4% | 1470 | 108 | 92.7% | 94.3% | 94.1% |
| `src/pystachy_compiler/calls.py` | 1332 | 51 | 96.2% | 810 | 52 | 93.6% | 95.2% | 92.9% |
| `src/pystachy_compiler/containers.py` | 972 | 39 | 96.0% | 520 | 41 | 92.1% | 94.6% | 94.6% |
| `src/pystachy_compiler/conversions.py` | 305 | 14 | 95.4% | 198 | 10 | 94.9% | 95.2% | 95.2% |
| `src/pystachy_compiler/declarations.py` | 2354 | 142 | 94.0% | 1594 | 135 | 91.5% | 93.0% | 92.2% |
| `src/pystachy_compiler/diagnostics.py` | 82 | 8 | 90.2% | 20 | 1 | 95.0% | 91.2% | 91.2% |
| `src/pystachy_compiler/driver.py` | 595 | 80 | 86.6% | 244 | 49 | 79.9% | 84.6% | 69.1% |
| `src/pystachy_compiler/dynamic.py` | 3192 | 170 | 94.7% | 1764 | 205 | 88.4% | 92.4% | 92.4% |
| `src/pystachy_compiler/emission.py` | 513 | 14 | 97.3% | 164 | 11 | 93.3% | 96.3% | 96.0% |
| `src/pystachy_compiler/exceptions.py` | 1182 | 36 | 97.0% | 562 | 33 | 94.1% | 96.0% | 96.0% |
| `src/pystachy_compiler/expressions.py` | 4170 | 131 | 96.9% | 2412 | 120 | 95.0% | 96.2% | 96.2% |
| `src/pystachy_compiler/flow.py` | 785 | 6 | 99.2% | 550 | 10 | 98.2% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 413 | 23 | 94.4% | 230 | 18 | 92.2% | 93.6% | 79.5% |
| `src/pystachy_compiler/gen.py` | 2589 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1010 | 36 | 96.4% | 402 | 42 | 89.6% | 94.5% | 94.5% |
| `src/pystachy_compiler/ir.py` | 384 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 411 | 27 | 93.4% | 336 | 27 | 92.0% | 92.8% | 78.7% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2558 | 73 | 97.1% | 1574 | 80 | 94.9% | 96.3% | 96.1% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 415 | 12 | 97.1% | 226 | 9 | 96.0% | 96.7% | 56.6% |
| `src/pystachy_compiler/lowering.py` | 478 | 3 | 99.4% | 290 | 5 | 98.3% | 99.0% | 98.8% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 31 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1016 | 18 | 98.2% | 636 | 30 | 95.3% | 97.1% | 96.7% |
| `src/pystachy_compiler/parser.py` | 2009 | 103 | 94.9% | 1112 | 101 | 90.9% | 93.5% | 93.5% |
| `src/pystachy_compiler/program.py` | 944 | 35 | 96.3% | 692 | 33 | 95.2% | 95.8% | 94.9% |
| `src/pystachy_compiler/reflection.py` | 1962 | 144 | 92.7% | 1046 | 136 | 87.0% | 90.7% | 90.6% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 254 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1704 | 65 | 96.2% | 938 | 69 | 92.6% | 94.9% | 94.8% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 147 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 765 | 38 | 95.0% | 456 | 46 | 89.9% | 93.1% | 93.1% |
| `src/pystachy_compiler/union_arithmetic.py` | 133 | 3 | 97.7% | 52 | 3 | 94.2% | 96.8% | 96.8% |
| `src/pystachy_compiler/union_proof.py` | 773 | 13 | 98.3% | 554 | 23 | 95.8% | 97.3% | 92.5% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 458 | 29 | 93.7% | 246 | 27 | 89.0% | 92.0% | 92.0% |
| `src/pystachy_compiler/utils.py` | 661 | 28 | 95.8% | 332 | 27 | 91.9% | 94.5% | 93.8% |
| `src/pystachy_compiler/variables.py` | 1786 | 100 | 94.4% | 1116 | 108 | 90.3% | 92.8% | 92.8% |
