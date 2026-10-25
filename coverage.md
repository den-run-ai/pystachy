## Hosted compiler coverage

Commit `6f5b169bc289e31d0c0c783a01329b06c01f7e62`: statements **95.9%** (36979 of 38552) and branches **92.5%** (19558 of 21152); 94.7% together, coverage.py's total. 5 suites, 5794 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5544 passed, 0 failed | 5552 | 2525 s | 94.7% | 90.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 141 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 128 | 76 s | 38.1% | 29.8% |
| cache | `tests/cache.sh` | 67 passed, 0 failed | 33 | 234 s | 29.4% | 19.9% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 142 tests, OK | 2 | 15 s | 49.9% | 42.5% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 79 programs | 79 | 76 s | 59.0% | 51.8% |
| **all** | | | **5794** | | **95.9%** | **92.5%** |

The other suites run 475 statements and 349 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1487 | 72 | 95.2% | 1270 | 84 | 93.4% | 94.3% | 94.3% |
| `src/pystachy_compiler/builtins.py` | 2272 | 103 | 95.5% | 1354 | 99 | 92.7% | 94.4% | 94.2% |
| `src/pystachy_compiler/calls.py` | 1307 | 54 | 95.9% | 800 | 55 | 93.1% | 94.8% | 92.5% |
| `src/pystachy_compiler/containers.py` | 843 | 32 | 96.2% | 454 | 34 | 92.5% | 94.9% | 94.9% |
| `src/pystachy_compiler/conversions.py` | 262 | 8 | 96.9% | 158 | 6 | 96.2% | 96.7% | 96.7% |
| `src/pystachy_compiler/declarations.py` | 2308 | 143 | 93.8% | 1556 | 133 | 91.5% | 92.9% | 92.1% |
| `src/pystachy_compiler/diagnostics.py` | 48 | 0 | 100.0% | 14 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 576 | 77 | 86.6% | 236 | 48 | 79.7% | 84.6% | 68.6% |
| `src/pystachy_compiler/dynamic.py` | 1845 | 126 | 93.2% | 980 | 144 | 85.3% | 90.4% | 90.4% |
| `src/pystachy_compiler/emission.py` | 492 | 13 | 97.4% | 148 | 10 | 93.2% | 96.4% | 96.1% |
| `src/pystachy_compiler/exceptions.py` | 1169 | 34 | 97.1% | 554 | 30 | 94.6% | 96.3% | 96.3% |
| `src/pystachy_compiler/expressions.py` | 3669 | 102 | 97.2% | 2144 | 108 | 95.0% | 96.4% | 96.4% |
| `src/pystachy_compiler/flow.py` | 777 | 6 | 99.2% | 544 | 10 | 98.2% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 344 | 13 | 96.2% | 190 | 10 | 94.7% | 95.7% | 78.7% |
| `src/pystachy_compiler/gen.py` | 2289 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 926 | 40 | 95.7% | 372 | 45 | 87.9% | 93.5% | 93.5% |
| `src/pystachy_compiler/ir.py` | 359 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 394 | 26 | 93.4% | 324 | 26 | 92.0% | 92.8% | 77.4% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2530 | 75 | 97.0% | 1560 | 82 | 94.7% | 96.2% | 95.9% |
| `src/pystachy_compiler/local_versions.py` | 38 | 0 | 100.0% | 26 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 365 | 11 | 97.0% | 190 | 8 | 95.8% | 96.6% | 52.1% |
| `src/pystachy_compiler/lowering.py` | 403 | 4 | 99.0% | 246 | 5 | 98.0% | 98.6% | 98.5% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 30 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 811 | 12 | 98.5% | 514 | 24 | 95.3% | 97.3% | 97.0% |
| `src/pystachy_compiler/parser.py` | 1999 | 103 | 94.8% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 937 | 35 | 96.3% | 686 | 33 | 95.2% | 95.8% | 94.8% |
| `src/pystachy_compiler/reflection.py` | 1936 | 145 | 92.5% | 1030 | 138 | 86.6% | 90.5% | 90.3% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 241 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1647 | 65 | 96.1% | 910 | 69 | 92.4% | 94.8% | 94.6% |
| `src/pystachy_compiler/structs.py` | 224 | 27 | 87.9% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 146 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 737 | 39 | 94.7% | 444 | 47 | 89.4% | 92.7% | 92.7% |
| `src/pystachy_compiler/union_arithmetic.py` | 115 | 3 | 97.4% | 50 | 3 | 94.0% | 96.4% | 96.4% |
| `src/pystachy_compiler/union_proof.py` | 766 | 12 | 98.4% | 548 | 22 | 96.0% | 97.4% | 92.3% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 419 | 29 | 93.1% | 222 | 27 | 87.8% | 91.3% | 91.3% |
| `src/pystachy_compiler/utils.py` | 634 | 27 | 95.7% | 318 | 26 | 91.8% | 94.4% | 93.7% |
| `src/pystachy_compiler/variables.py` | 1723 | 99 | 94.3% | 1074 | 104 | 90.3% | 92.7% | 92.7% |
