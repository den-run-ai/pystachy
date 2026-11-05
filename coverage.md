## Hosted compiler coverage

Commit `d81279361d847c4647e64bddb9dcb2466fd58711`: statements **96.0%** (43557 of 45377) and branches **92.5%** (22875 of 24724); 94.8% together, coverage.py's total. 5 suites, 6925 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 6654 passed, 0 failed | 6662 | 3903 s | 94.9% | 91.1% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 151 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 133 | 178 s | 48.9% | 41.0% |
| cache | `tests/cache.sh` | 68 passed, 0 failed | 34 | 230 s | 27.6% | 18.3% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 189 tests, OK | 2 | 12 s | 48.6% | 41.3% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 94 programs | 94 | 178 s | 61.3% | 54.5% |
| **all** | | | **6925** | | **96.0%** | **92.5%** |

The other suites run 493 statements and 363 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1576 | 70 | 95.6% | 1338 | 82 | 93.9% | 94.8% | 94.7% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 969 | 38 | 96.1% | 400 | 42 | 89.5% | 94.2% | 94.2% |
| `src/pystachy_compiler/builtins.py` | 2534 | 118 | 95.3% | 1532 | 112 | 92.7% | 94.3% | 94.1% |
| `src/pystachy_compiler/calls.py` | 1371 | 49 | 96.4% | 832 | 48 | 94.2% | 95.6% | 93.4% |
| `src/pystachy_compiler/containers.py` | 972 | 36 | 96.3% | 520 | 38 | 92.7% | 95.0% | 95.0% |
| `src/pystachy_compiler/conversions.py` | 307 | 13 | 95.8% | 200 | 9 | 95.5% | 95.7% | 95.7% |
| `src/pystachy_compiler/declarations.py` | 2375 | 140 | 94.1% | 1606 | 133 | 91.7% | 93.1% | 92.4% |
| `src/pystachy_compiler/diagnostics.py` | 84 | 8 | 90.5% | 20 | 1 | 95.0% | 91.3% | 91.3% |
| `src/pystachy_compiler/driver.py` | 611 | 80 | 86.9% | 248 | 49 | 80.2% | 85.0% | 69.6% |
| `src/pystachy_compiler/dynamic.py` | 3381 | 170 | 95.0% | 1800 | 206 | 88.6% | 92.7% | 92.7% |
| `src/pystachy_compiler/emission.py` | 526 | 15 | 97.1% | 170 | 12 | 92.9% | 96.1% | 95.3% |
| `src/pystachy_compiler/exceptions.py` | 1255 | 42 | 96.7% | 618 | 39 | 93.7% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 4215 | 130 | 96.9% | 2448 | 120 | 95.1% | 96.2% | 96.2% |
| `src/pystachy_compiler/flow.py` | 785 | 4 | 99.5% | 550 | 9 | 98.4% | 99.0% | 98.4% |
| `src/pystachy_compiler/functions.py` | 413 | 23 | 94.4% | 230 | 17 | 92.6% | 93.8% | 79.6% |
| `src/pystachy_compiler/gen.py` | 2647 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1010 | 36 | 96.4% | 402 | 42 | 89.6% | 94.5% | 94.5% |
| `src/pystachy_compiler/ir.py` | 391 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 415 | 27 | 93.5% | 340 | 27 | 92.1% | 92.8% | 78.7% |
| `src/pystachy_compiler/lexer.py` | 636 | 26 | 95.9% | 356 | 25 | 93.0% | 94.9% | 94.9% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2979 | 111 | 96.3% | 1864 | 120 | 93.6% | 95.2% | 95.0% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 434 | 12 | 97.2% | 232 | 9 | 96.1% | 96.8% | 58.3% |
| `src/pystachy_compiler/lowering.py` | 489 | 4 | 99.2% | 296 | 6 | 98.0% | 98.7% | 98.6% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 31 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 28 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1158 | 25 | 97.8% | 732 | 36 | 95.1% | 96.8% | 96.1% |
| `src/pystachy_compiler/parser.py` | 2091 | 104 | 95.0% | 1168 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/program.py` | 1023 | 37 | 96.4% | 756 | 37 | 95.1% | 95.8% | 95.0% |
| `src/pystachy_compiler/reflection.py` | 2399 | 167 | 93.0% | 1260 | 161 | 87.2% | 91.0% | 90.9% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 260 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1719 | 62 | 96.4% | 946 | 68 | 92.8% | 95.1% | 95.0% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 154 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 799 | 38 | 95.2% | 478 | 46 | 90.4% | 93.4% | 93.4% |
| `src/pystachy_compiler/union_arithmetic.py` | 133 | 3 | 97.7% | 52 | 3 | 94.2% | 96.8% | 96.8% |
| `src/pystachy_compiler/union_proof.py` | 793 | 13 | 98.4% | 570 | 23 | 96.0% | 97.4% | 92.7% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 458 | 23 | 95.0% | 246 | 23 | 90.7% | 93.5% | 93.5% |
| `src/pystachy_compiler/utils.py` | 715 | 31 | 95.7% | 364 | 30 | 91.8% | 94.3% | 92.2% |
| `src/pystachy_compiler/variables.py` | 1821 | 102 | 94.4% | 1138 | 110 | 90.3% | 92.8% | 92.8% |
