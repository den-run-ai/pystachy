## Hosted compiler coverage

Commit `dcdc1a281d218038c2041a5e381396edd43beaea`: statements **95.9%** (36290 of 37823) and branches **92.6%** (19201 of 20740); 94.8% together, coverage.py's total. 5 suites, 5718 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5470 passed, 0 failed | 5478 | 2320 s | 94.7% | 90.9% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 139 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 126 | 132 s | 37.7% | 29.5% |
| cache | `tests/cache.sh` | 67 passed, 0 failed | 33 | 227 s | 29.6% | 20.2% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 140 tests, OK | 2 | 15 s | 50.4% | 43.0% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 79 programs | 79 | 130 s | 59.0% | 51.8% |
| **all** | | | **5718** | | **95.9%** | **92.6%** |

The other suites run 468 statements and 344 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1442 | 73 | 94.9% | 1234 | 84 | 93.2% | 94.1% | 94.1% |
| `src/pystachy_compiler/builtins.py` | 2218 | 100 | 95.5% | 1316 | 96 | 92.7% | 94.5% | 94.2% |
| `src/pystachy_compiler/calls.py` | 1211 | 52 | 95.7% | 750 | 52 | 93.1% | 94.7% | 92.2% |
| `src/pystachy_compiler/containers.py` | 802 | 32 | 96.0% | 440 | 34 | 92.3% | 94.7% | 94.7% |
| `src/pystachy_compiler/conversions.py` | 258 | 8 | 96.9% | 156 | 6 | 96.2% | 96.6% | 96.6% |
| `src/pystachy_compiler/declarations.py` | 2293 | 143 | 93.8% | 1546 | 133 | 91.4% | 92.8% | 92.1% |
| `src/pystachy_compiler/diagnostics.py` | 48 | 0 | 100.0% | 14 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 575 | 77 | 86.6% | 236 | 48 | 79.7% | 84.6% | 68.6% |
| `src/pystachy_compiler/dynamic.py` | 1673 | 99 | 94.1% | 852 | 106 | 87.6% | 91.9% | 91.9% |
| `src/pystachy_compiler/emission.py` | 486 | 13 | 97.3% | 144 | 10 | 93.1% | 96.3% | 96.0% |
| `src/pystachy_compiler/exceptions.py` | 1164 | 33 | 97.2% | 550 | 29 | 94.7% | 96.4% | 96.4% |
| `src/pystachy_compiler/expressions.py` | 3528 | 99 | 97.2% | 2094 | 103 | 95.1% | 96.4% | 96.4% |
| `src/pystachy_compiler/flow.py` | 766 | 6 | 99.2% | 534 | 10 | 98.1% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 326 | 10 | 96.9% | 180 | 8 | 95.6% | 96.4% | 78.5% |
| `src/pystachy_compiler/gen.py` | 2267 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 926 | 40 | 95.7% | 372 | 45 | 87.9% | 93.5% | 93.5% |
| `src/pystachy_compiler/ir.py` | 351 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 394 | 26 | 93.4% | 324 | 26 | 92.0% | 92.8% | 77.4% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2530 | 75 | 97.0% | 1560 | 82 | 94.7% | 96.2% | 95.9% |
| `src/pystachy_compiler/local_versions.py` | 38 | 0 | 100.0% | 26 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 359 | 11 | 96.9% | 186 | 7 | 96.2% | 96.7% | 53.0% |
| `src/pystachy_compiler/lowering.py` | 394 | 3 | 99.2% | 238 | 4 | 98.3% | 98.9% | 98.7% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 30 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 811 | 13 | 98.4% | 514 | 25 | 95.1% | 97.1% | 96.8% |
| `src/pystachy_compiler/parser.py` | 1999 | 103 | 94.8% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 934 | 35 | 96.3% | 684 | 33 | 95.2% | 95.8% | 94.8% |
| `src/pystachy_compiler/reflection.py` | 1925 | 145 | 92.5% | 1024 | 138 | 86.5% | 90.4% | 90.3% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 241 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1629 | 63 | 96.1% | 898 | 67 | 92.5% | 94.9% | 94.7% |
| `src/pystachy_compiler/structs.py` | 224 | 27 | 87.9% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 146 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 720 | 39 | 94.6% | 436 | 47 | 89.2% | 92.6% | 92.6% |
| `src/pystachy_compiler/union_arithmetic.py` | 115 | 3 | 97.4% | 50 | 3 | 94.0% | 96.4% | 96.4% |
| `src/pystachy_compiler/union_proof.py` | 762 | 13 | 98.3% | 544 | 23 | 95.8% | 97.2% | 92.2% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 419 | 29 | 93.1% | 222 | 27 | 87.8% | 91.3% | 91.3% |
| `src/pystachy_compiler/utils.py` | 624 | 26 | 95.8% | 314 | 25 | 92.0% | 94.6% | 93.8% |
| `src/pystachy_compiler/variables.py` | 1711 | 99 | 94.2% | 1066 | 104 | 90.2% | 92.7% | 92.7% |
