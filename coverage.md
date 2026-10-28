## Hosted compiler coverage

Commit `5bd492b33cd6bc32fb464d008d543560a8959486`: statements **96.0%** (39868 of 41534) and branches **92.5%** (20929 of 22620); 94.8% together, coverage.py's total. 5 suites, 6228 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5975 passed, 0 failed | 5983 | 2966 s | 94.8% | 91.0% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 143 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 130 | 135 s | 37.1% | 28.7% |
| cache | `tests/cache.sh` | 68 passed, 0 failed | 34 | 184 s | 28.4% | 19.0% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 142 tests, OK | 2 | 9 s | 47.9% | 40.5% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 79 programs | 79 | 141 s | 56.7% | 49.7% |
| **all** | | | **6228** | | **96.0%** | **92.5%** |

The other suites run 476 statements and 350 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1489 | 72 | 95.2% | 1272 | 83 | 93.5% | 94.4% | 94.3% |
| `src/pystachy_compiler/bigints.py` | 933 | 39 | 95.8% | 386 | 42 | 89.1% | 93.9% | 93.9% |
| `src/pystachy_compiler/builtins.py` | 2406 | 112 | 95.3% | 1460 | 107 | 92.7% | 94.3% | 94.1% |
| `src/pystachy_compiler/calls.py` | 1316 | 52 | 96.0% | 806 | 53 | 93.4% | 95.1% | 92.7% |
| `src/pystachy_compiler/containers.py` | 893 | 33 | 96.3% | 494 | 35 | 92.9% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 299 | 10 | 96.7% | 194 | 8 | 95.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/declarations.py` | 2350 | 142 | 94.0% | 1592 | 135 | 91.5% | 93.0% | 92.2% |
| `src/pystachy_compiler/diagnostics.py` | 66 | 0 | 100.0% | 18 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 576 | 77 | 86.6% | 236 | 48 | 79.7% | 84.6% | 68.6% |
| `src/pystachy_compiler/dynamic.py` | 2609 | 152 | 94.2% | 1428 | 182 | 87.3% | 91.7% | 91.7% |
| `src/pystachy_compiler/emission.py` | 511 | 14 | 97.3% | 162 | 11 | 93.2% | 96.3% | 96.0% |
| `src/pystachy_compiler/exceptions.py` | 1176 | 34 | 97.1% | 558 | 30 | 94.6% | 96.3% | 96.3% |
| `src/pystachy_compiler/expressions.py` | 4081 | 130 | 96.8% | 2352 | 120 | 94.9% | 96.1% | 96.1% |
| `src/pystachy_compiler/flow.py` | 785 | 6 | 99.2% | 550 | 10 | 98.2% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 365 | 13 | 96.4% | 200 | 10 | 95.0% | 95.9% | 79.8% |
| `src/pystachy_compiler/gen.py` | 2493 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 994 | 36 | 96.4% | 398 | 42 | 89.4% | 94.4% | 94.4% |
| `src/pystachy_compiler/ir.py` | 363 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 404 | 27 | 93.3% | 330 | 27 | 91.8% | 92.6% | 77.4% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2546 | 73 | 97.1% | 1566 | 80 | 94.9% | 96.3% | 96.0% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 371 | 11 | 97.0% | 192 | 8 | 95.8% | 96.6% | 51.9% |
| `src/pystachy_compiler/lowering.py` | 418 | 3 | 99.3% | 256 | 4 | 98.4% | 99.0% | 98.8% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 30 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 811 | 12 | 98.5% | 514 | 24 | 95.3% | 97.3% | 97.0% |
| `src/pystachy_compiler/parser.py` | 2001 | 103 | 94.9% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 939 | 35 | 96.3% | 688 | 33 | 95.2% | 95.8% | 94.8% |
| `src/pystachy_compiler/reflection.py` | 1958 | 143 | 92.7% | 1044 | 136 | 87.0% | 90.7% | 90.6% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 249 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1678 | 65 | 96.1% | 928 | 69 | 92.6% | 94.9% | 94.7% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 146 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 764 | 38 | 95.0% | 456 | 46 | 89.9% | 93.1% | 93.1% |
| `src/pystachy_compiler/union_arithmetic.py` | 133 | 3 | 97.7% | 52 | 3 | 94.2% | 96.8% | 96.8% |
| `src/pystachy_compiler/union_proof.py` | 769 | 12 | 98.4% | 550 | 22 | 96.0% | 97.4% | 92.6% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 431 | 27 | 93.7% | 232 | 25 | 89.2% | 92.2% | 92.2% |
| `src/pystachy_compiler/utils.py` | 651 | 27 | 95.9% | 326 | 26 | 92.0% | 94.6% | 93.9% |
| `src/pystachy_compiler/variables.py` | 1778 | 100 | 94.4% | 1114 | 108 | 90.3% | 92.8% | 92.8% |
