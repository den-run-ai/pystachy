## Hosted compiler coverage

Commit `9b391645d32b87b4eba8784600cf0a6743d56556`: statements **95.9%** (38288 of 39923) and branches **92.4%** (20235 of 21892); 94.7% together, coverage.py's total. 5 suites, 5954 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5703 passed, 0 failed | 5711 | 2775 s | 94.7% | 90.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 141 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 128 | 125 s | 37.3% | 29.1% |
| cache | `tests/cache.sh` | 68 passed, 0 failed | 34 | 199 s | 28.8% | 19.4% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 142 tests, OK | 2 | 11 s | 48.8% | 41.4% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 79 programs | 79 | 136 s | 57.9% | 50.6% |
| **all** | | | **5954** | | **95.9%** | **92.4%** |

The other suites run 475 statements and 349 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1487 | 72 | 95.2% | 1270 | 84 | 93.4% | 94.3% | 94.3% |
| `src/pystachy_compiler/bigints.py` | 276 | 7 | 97.5% | 110 | 8 | 92.7% | 96.1% | 96.1% |
| `src/pystachy_compiler/builtins.py` | 2318 | 107 | 95.4% | 1390 | 103 | 92.6% | 94.3% | 94.1% |
| `src/pystachy_compiler/calls.py` | 1309 | 55 | 95.8% | 802 | 56 | 93.0% | 94.7% | 92.4% |
| `src/pystachy_compiler/containers.py` | 855 | 32 | 96.3% | 464 | 34 | 92.7% | 95.0% | 95.0% |
| `src/pystachy_compiler/conversions.py` | 276 | 8 | 97.1% | 172 | 6 | 96.5% | 96.9% | 96.9% |
| `src/pystachy_compiler/declarations.py` | 2341 | 142 | 93.9% | 1582 | 134 | 91.5% | 93.0% | 92.2% |
| `src/pystachy_compiler/diagnostics.py` | 56 | 0 | 100.0% | 14 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 576 | 77 | 86.6% | 236 | 48 | 79.7% | 84.6% | 68.6% |
| `src/pystachy_compiler/dynamic.py` | 2310 | 154 | 93.3% | 1298 | 182 | 86.0% | 90.7% | 90.7% |
| `src/pystachy_compiler/emission.py` | 494 | 13 | 97.4% | 150 | 10 | 93.3% | 96.4% | 96.1% |
| `src/pystachy_compiler/exceptions.py` | 1169 | 34 | 97.1% | 554 | 30 | 94.6% | 96.3% | 96.3% |
| `src/pystachy_compiler/expressions.py` | 3952 | 126 | 96.8% | 2278 | 118 | 94.8% | 96.1% | 96.1% |
| `src/pystachy_compiler/flow.py` | 785 | 6 | 99.2% | 550 | 10 | 98.2% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 351 | 13 | 96.3% | 192 | 10 | 94.8% | 95.8% | 79.0% |
| `src/pystachy_compiler/gen.py` | 2356 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 926 | 40 | 95.7% | 372 | 45 | 87.9% | 93.5% | 93.5% |
| `src/pystachy_compiler/ir.py` | 363 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 399 | 27 | 93.2% | 328 | 27 | 91.8% | 92.6% | 77.4% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2540 | 75 | 97.0% | 1562 | 82 | 94.8% | 96.2% | 95.9% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 365 | 11 | 97.0% | 190 | 8 | 95.8% | 96.6% | 52.1% |
| `src/pystachy_compiler/lowering.py` | 408 | 3 | 99.3% | 250 | 4 | 98.4% | 98.9% | 98.8% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 30 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 811 | 12 | 98.5% | 514 | 23 | 95.5% | 97.4% | 97.1% |
| `src/pystachy_compiler/parser.py` | 2001 | 103 | 94.9% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 938 | 35 | 96.3% | 686 | 33 | 95.2% | 95.8% | 94.8% |
| `src/pystachy_compiler/reflection.py` | 1957 | 145 | 92.6% | 1042 | 138 | 86.8% | 90.6% | 90.4% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 242 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1651 | 65 | 96.1% | 912 | 69 | 92.4% | 94.8% | 94.7% |
| `src/pystachy_compiler/structs.py` | 224 | 27 | 87.9% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 146 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 753 | 38 | 95.0% | 452 | 46 | 89.8% | 93.0% | 93.0% |
| `src/pystachy_compiler/union_arithmetic.py` | 131 | 3 | 97.7% | 52 | 3 | 94.2% | 96.7% | 96.7% |
| `src/pystachy_compiler/union_proof.py` | 766 | 12 | 98.4% | 548 | 22 | 96.0% | 97.4% | 92.3% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 423 | 27 | 93.6% | 226 | 25 | 88.9% | 92.0% | 92.0% |
| `src/pystachy_compiler/utils.py` | 643 | 28 | 95.6% | 322 | 27 | 91.6% | 94.3% | 93.6% |
| `src/pystachy_compiler/variables.py` | 1768 | 100 | 94.3% | 1108 | 108 | 90.3% | 92.8% | 92.7% |
