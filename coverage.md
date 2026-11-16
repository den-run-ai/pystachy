## Hosted compiler coverage

Commit `3da553ee569d519031508f2177cdb04f9f436991`: statements **95.7%** (50005 of 52231) and branches **92.3%** (26085 of 28254); 94.5% together, coverage.py's total. 5 suites, 8008 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 7660 passed, 0 failed | 7670 | 4154 s | 92.6% | 88.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 194 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 175 | 192 s | 48.5% | 41.3% |
| cache | `tests/cache.sh` | 97 passed, 0 failed | 51 | 367 s | 27.2% | 18.1% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 551 tests, OK | 9 | 87 s | 51.9% | 45.1% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 103 programs | 103 | 170 s | 59.4% | 53.1% |
| **all** | | | **8008** | | **95.7%** | **92.3%** |

The other suites run 1628 statements and 994 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1602 | 73 | 95.4% | 1360 | 86 | 93.7% | 94.6% | 94.6% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 996 | 38 | 96.2% | 410 | 42 | 89.8% | 94.3% | 94.3% |
| `src/pystachy_compiler/builtins.py` | 2843 | 137 | 95.2% | 1704 | 135 | 92.1% | 94.0% | 93.0% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 226 | 59 | 73.9% | 110 | 35 | 68.2% | 72.0% | 13.7% |
| `src/pystachy_compiler/callbacks.py` | 180 | 2 | 98.9% | 90 | 3 | 96.7% | 98.1% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1460 | 52 | 96.4% | 884 | 51 | 94.2% | 95.6% | 93.7% |
| `src/pystachy_compiler/containers.py` | 1057 | 40 | 96.2% | 576 | 40 | 93.1% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 315 | 10 | 96.8% | 204 | 8 | 96.1% | 96.5% | 96.5% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/declarations.py` | 2498 | 140 | 94.4% | 1694 | 134 | 92.1% | 93.5% | 92.8% |
| `src/pystachy_compiler/diagnostics.py` | 86 | 8 | 90.7% | 20 | 1 | 95.0% | 91.5% | 91.5% |
| `src/pystachy_compiler/driver.py` | 1055 | 165 | 84.4% | 448 | 115 | 74.3% | 81.4% | 64.9% |
| `src/pystachy_compiler/dynamic.py` | 4046 | 225 | 94.4% | 2106 | 248 | 88.2% | 92.3% | 92.3% |
| `src/pystachy_compiler/dynamic_proof.py` | 409 | 4 | 99.0% | 248 | 7 | 97.2% | 98.3% | 93.2% |
| `src/pystachy_compiler/emission.py` | 553 | 16 | 97.1% | 182 | 13 | 92.9% | 96.1% | 94.1% |
| `src/pystachy_compiler/exceptions.py` | 1499 | 50 | 96.7% | 726 | 45 | 93.8% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 5037 | 145 | 97.1% | 2870 | 145 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/flow.py` | 828 | 4 | 99.5% | 576 | 9 | 98.4% | 99.1% | 98.4% |
| `src/pystachy_compiler/functions.py` | 414 | 23 | 94.4% | 230 | 17 | 92.6% | 93.8% | 79.7% |
| `src/pystachy_compiler/gen.py` | 2809 | 2 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1048 | 37 | 96.5% | 412 | 41 | 90.0% | 94.7% | 94.7% |
| `src/pystachy_compiler/ir.py` | 430 | 3 | 99.3% | 32 | 3 | 90.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/ircheck.py` | 475 | 27 | 94.3% | 394 | 27 | 93.1% | 93.8% | 78.3% |
| `src/pystachy_compiler/lexer.py` | 636 | 26 | 95.9% | 356 | 25 | 93.0% | 94.9% | 94.9% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 3020 | 113 | 96.3% | 1886 | 122 | 93.5% | 95.2% | 95.0% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 446 | 11 | 97.5% | 240 | 7 | 97.1% | 97.4% | 58.6% |
| `src/pystachy_compiler/lowering.py` | 536 | 3 | 99.4% | 310 | 5 | 98.4% | 99.1% | 98.9% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 31 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 28 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1662 | 34 | 98.0% | 1004 | 40 | 96.0% | 97.2% | 96.7% |
| `src/pystachy_compiler/parser.py` | 2098 | 104 | 95.0% | 1170 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 235 | 15 | 93.6% | 132 | 13 | 90.2% | 92.4% | 92.4% |
| `src/pystachy_compiler/program.py` | 1308 | 52 | 96.0% | 976 | 55 | 94.4% | 95.3% | 94.7% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2558 | 167 | 93.5% | 1360 | 165 | 87.9% | 91.5% | 91.4% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 128 | 1 | 99.2% | 60 | 4 | 93.3% | 97.3% | 18.1% |
| `src/pystachy_compiler/specs.py` | 271 | 0 | 100.0% | 86 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1774 | 64 | 96.4% | 980 | 70 | 92.9% | 95.1% | 95.0% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 154 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 818 | 37 | 95.5% | 488 | 45 | 90.8% | 93.7% | 93.7% |
| `src/pystachy_compiler/union_arithmetic.py` | 142 | 3 | 97.9% | 56 | 3 | 94.6% | 97.0% | 97.0% |
| `src/pystachy_compiler/union_proof.py` | 851 | 14 | 98.4% | 608 | 24 | 96.1% | 97.4% | 91.6% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 465 | 23 | 95.1% | 250 | 23 | 90.8% | 93.6% | 93.6% |
| `src/pystachy_compiler/utils.py` | 775 | 26 | 96.6% | 400 | 26 | 93.5% | 95.6% | 92.2% |
| `src/pystachy_compiler/variables.py` | 1827 | 102 | 94.4% | 1142 | 110 | 90.4% | 92.9% | 92.8% |
