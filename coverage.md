## Hosted compiler coverage

Commit `de65c6fbfeb101e46f25e59f5940dd51b4cdb369`: statements **95.9%** (37761 of 39383) and branches **92.4%** (19994 of 21638); 94.6% together, coverage.py's total. 5 suites, 5906 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5655 passed, 0 failed | 5663 | 2687 s | 94.7% | 90.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 141 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 128 | 101 s | 37.5% | 29.3% |
| cache | `tests/cache.sh` | 68 passed, 0 failed | 34 | 159 s | 28.9% | 19.5% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 142 tests, OK | 2 | 9 s | 49.1% | 41.7% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 79 programs | 79 | 104 s | 58.1% | 50.9% |
| **all** | | | **5906** | | **95.9%** | **92.4%** |

The other suites run 475 statements and 349 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1487 | 72 | 95.2% | 1270 | 84 | 93.4% | 94.3% | 94.3% |
| `src/pystachy_compiler/builtins.py` | 2294 | 106 | 95.4% | 1370 | 102 | 92.6% | 94.3% | 94.1% |
| `src/pystachy_compiler/calls.py` | 1309 | 55 | 95.8% | 802 | 56 | 93.0% | 94.7% | 92.4% |
| `src/pystachy_compiler/containers.py` | 849 | 32 | 96.2% | 458 | 34 | 92.6% | 95.0% | 95.0% |
| `src/pystachy_compiler/conversions.py` | 262 | 8 | 96.9% | 158 | 6 | 96.2% | 96.7% | 96.7% |
| `src/pystachy_compiler/declarations.py` | 2329 | 141 | 93.9% | 1572 | 133 | 91.5% | 93.0% | 92.2% |
| `src/pystachy_compiler/diagnostics.py` | 48 | 0 | 100.0% | 14 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 576 | 77 | 86.6% | 236 | 48 | 79.7% | 84.6% | 68.6% |
| `src/pystachy_compiler/dynamic.py` | 2310 | 154 | 93.3% | 1298 | 182 | 86.0% | 90.7% | 90.7% |
| `src/pystachy_compiler/emission.py` | 492 | 13 | 97.4% | 148 | 10 | 93.2% | 96.4% | 96.1% |
| `src/pystachy_compiler/exceptions.py` | 1169 | 34 | 97.1% | 554 | 30 | 94.6% | 96.3% | 96.3% |
| `src/pystachy_compiler/expressions.py` | 3845 | 122 | 96.8% | 2206 | 114 | 94.8% | 96.1% | 96.1% |
| `src/pystachy_compiler/flow.py` | 785 | 6 | 99.2% | 550 | 10 | 98.2% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 350 | 13 | 96.3% | 192 | 10 | 94.8% | 95.8% | 79.0% |
| `src/pystachy_compiler/gen.py` | 2299 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 926 | 40 | 95.7% | 372 | 45 | 87.9% | 93.5% | 93.5% |
| `src/pystachy_compiler/ir.py` | 363 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 394 | 26 | 93.4% | 324 | 26 | 92.0% | 92.8% | 77.4% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2530 | 75 | 97.0% | 1560 | 82 | 94.7% | 96.2% | 95.9% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 365 | 11 | 97.0% | 190 | 8 | 95.8% | 96.6% | 52.1% |
| `src/pystachy_compiler/lowering.py` | 403 | 4 | 99.0% | 246 | 5 | 98.0% | 98.6% | 98.5% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 30 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 811 | 12 | 98.5% | 514 | 24 | 95.3% | 97.3% | 97.0% |
| `src/pystachy_compiler/parser.py` | 1999 | 103 | 94.8% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 938 | 35 | 96.3% | 686 | 33 | 95.2% | 95.8% | 94.8% |
| `src/pystachy_compiler/reflection.py` | 1955 | 145 | 92.6% | 1040 | 138 | 86.7% | 90.6% | 90.4% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 241 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1651 | 65 | 96.1% | 912 | 69 | 92.4% | 94.8% | 94.7% |
| `src/pystachy_compiler/structs.py` | 224 | 27 | 87.9% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 146 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 753 | 38 | 95.0% | 452 | 46 | 89.8% | 93.0% | 93.0% |
| `src/pystachy_compiler/union_arithmetic.py` | 131 | 3 | 97.7% | 52 | 3 | 94.2% | 96.7% | 96.7% |
| `src/pystachy_compiler/union_proof.py` | 766 | 12 | 98.4% | 548 | 22 | 96.0% | 97.4% | 92.3% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 421 | 28 | 93.3% | 224 | 26 | 88.4% | 91.6% | 91.6% |
| `src/pystachy_compiler/utils.py` | 639 | 27 | 95.8% | 318 | 26 | 91.8% | 94.5% | 93.7% |
| `src/pystachy_compiler/variables.py` | 1766 | 100 | 94.3% | 1106 | 108 | 90.2% | 92.8% | 92.7% |
