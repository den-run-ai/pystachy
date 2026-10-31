## Hosted compiler coverage

Commit `06e3ad5d08514ba31fb231fe4636a962fe6578e3`: statements **96.0%** (40958 of 42665) and branches **92.5%** (21448 of 23182); 94.8% together, coverage.py's total. 5 suites, 6359 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 6104 passed, 0 failed | 6112 | 2981 s | 94.9% | 91.0% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 143 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 130 | 137 s | 36.8% | 28.4% |
| cache | `tests/cache.sh` | 68 passed, 0 failed | 34 | 186 s | 28.1% | 18.7% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 142 tests, OK | 2 | 8 s | 47.2% | 39.8% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 81 programs | 81 | 146 s | 57.1% | 50.2% |
| **all** | | | **6359** | | **96.0%** | **92.5%** |

The other suites run 476 statements and 350 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1578 | 72 | 95.4% | 1336 | 84 | 93.7% | 94.6% | 94.6% |
| `src/pystachy_compiler/bigints.py` | 993 | 39 | 96.1% | 412 | 43 | 89.6% | 94.2% | 94.2% |
| `src/pystachy_compiler/builtins.py` | 2436 | 112 | 95.4% | 1466 | 107 | 92.7% | 94.4% | 94.2% |
| `src/pystachy_compiler/calls.py` | 1332 | 51 | 96.2% | 810 | 52 | 93.6% | 95.2% | 92.9% |
| `src/pystachy_compiler/containers.py` | 972 | 39 | 96.0% | 520 | 41 | 92.1% | 94.6% | 94.6% |
| `src/pystachy_compiler/conversions.py` | 305 | 14 | 95.4% | 198 | 10 | 94.9% | 95.2% | 95.2% |
| `src/pystachy_compiler/declarations.py` | 2354 | 142 | 94.0% | 1594 | 135 | 91.5% | 93.0% | 92.2% |
| `src/pystachy_compiler/diagnostics.py` | 68 | 0 | 100.0% | 18 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 590 | 77 | 86.9% | 242 | 48 | 80.2% | 85.0% | 69.4% |
| `src/pystachy_compiler/dynamic.py` | 3192 | 170 | 94.7% | 1764 | 205 | 88.4% | 92.4% | 92.4% |
| `src/pystachy_compiler/emission.py` | 511 | 14 | 97.3% | 162 | 11 | 93.2% | 96.3% | 96.0% |
| `src/pystachy_compiler/exceptions.py` | 1178 | 36 | 96.9% | 560 | 32 | 94.3% | 96.1% | 96.1% |
| `src/pystachy_compiler/expressions.py` | 4131 | 131 | 96.8% | 2388 | 120 | 95.0% | 96.1% | 96.1% |
| `src/pystachy_compiler/flow.py` | 785 | 6 | 99.2% | 550 | 10 | 98.2% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 405 | 23 | 94.3% | 224 | 18 | 92.0% | 93.5% | 79.0% |
| `src/pystachy_compiler/gen.py` | 2573 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 995 | 36 | 96.4% | 398 | 42 | 89.4% | 94.4% | 94.4% |
| `src/pystachy_compiler/ir.py` | 378 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 404 | 27 | 93.3% | 330 | 27 | 91.8% | 92.6% | 77.4% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2558 | 73 | 97.1% | 1574 | 80 | 94.9% | 96.3% | 96.1% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 375 | 11 | 97.1% | 194 | 8 | 95.9% | 96.7% | 52.4% |
| `src/pystachy_compiler/lowering.py` | 418 | 3 | 99.3% | 256 | 4 | 98.4% | 99.0% | 98.8% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 31 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 811 | 12 | 98.5% | 514 | 24 | 95.3% | 97.3% | 97.0% |
| `src/pystachy_compiler/parser.py` | 2001 | 103 | 94.9% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 942 | 35 | 96.3% | 690 | 33 | 95.2% | 95.8% | 94.9% |
| `src/pystachy_compiler/reflection.py` | 1961 | 143 | 92.7% | 1046 | 136 | 87.0% | 90.7% | 90.6% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 249 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1704 | 65 | 96.2% | 938 | 69 | 92.6% | 94.9% | 94.8% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 146 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 765 | 38 | 95.0% | 456 | 46 | 89.9% | 93.1% | 93.1% |
| `src/pystachy_compiler/union_arithmetic.py` | 133 | 3 | 97.7% | 52 | 3 | 94.2% | 96.8% | 96.8% |
| `src/pystachy_compiler/union_proof.py` | 769 | 12 | 98.4% | 550 | 22 | 96.0% | 97.4% | 92.6% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 431 | 27 | 93.7% | 232 | 25 | 89.2% | 92.2% | 92.2% |
| `src/pystachy_compiler/utils.py` | 653 | 28 | 95.7% | 326 | 27 | 91.7% | 94.4% | 93.7% |
| `src/pystachy_compiler/variables.py` | 1786 | 100 | 94.4% | 1116 | 108 | 90.3% | 92.8% | 92.8% |
