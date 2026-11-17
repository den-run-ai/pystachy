## Hosted compiler coverage

Commit `71e14a88d9f261a50fa8f77986e17c0996b9c82b`: statements **95.7%** (50705 of 52973) and branches **92.3%** (26426 of 28636); 94.5% together, coverage.py's total. 5 suites, 8187 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 7839 passed, 0 failed | 7849 | 4332 s | 92.6% | 88.7% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 194 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 175 | 153 s | 48.4% | 41.1% |
| cache | `tests/cache.sh` | 97 passed, 0 failed | 51 | 367 s | 27.3% | 18.1% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 551 tests, OK | 9 | 85 s | 51.6% | 44.7% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 103 programs | 103 | 137 s | 59.2% | 52.8% |
| **all** | | | **8187** | | **95.7%** | **92.3%** |

The other suites run 1661 statements and 1021 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1602 | 72 | 95.5% | 1360 | 85 | 93.8% | 94.7% | 94.6% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 996 | 38 | 96.2% | 410 | 42 | 89.8% | 94.3% | 94.3% |
| `src/pystachy_compiler/builtins.py` | 2843 | 137 | 95.2% | 1704 | 135 | 92.1% | 94.0% | 93.0% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 226 | 59 | 73.9% | 110 | 35 | 68.2% | 72.0% | 13.7% |
| `src/pystachy_compiler/callbacks.py` | 180 | 2 | 98.9% | 90 | 3 | 96.7% | 98.1% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1467 | 52 | 96.5% | 890 | 51 | 94.3% | 95.6% | 93.8% |
| `src/pystachy_compiler/containers.py` | 1057 | 40 | 96.2% | 576 | 40 | 93.1% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 315 | 10 | 96.8% | 204 | 8 | 96.1% | 96.5% | 96.5% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/declarations.py` | 2599 | 144 | 94.5% | 1764 | 139 | 92.1% | 93.5% | 92.9% |
| `src/pystachy_compiler/diagnostics.py` | 93 | 8 | 91.4% | 22 | 1 | 95.5% | 92.2% | 92.2% |
| `src/pystachy_compiler/driver.py` | 1078 | 166 | 84.6% | 454 | 116 | 74.4% | 81.6% | 65.4% |
| `src/pystachy_compiler/dynamic.py` | 4214 | 253 | 94.0% | 2206 | 271 | 87.7% | 91.8% | 91.8% |
| `src/pystachy_compiler/dynamic_proof.py` | 409 | 4 | 99.0% | 248 | 7 | 97.2% | 98.3% | 93.2% |
| `src/pystachy_compiler/emission.py` | 553 | 16 | 97.1% | 182 | 13 | 92.9% | 96.1% | 94.1% |
| `src/pystachy_compiler/exceptions.py` | 1499 | 50 | 96.7% | 726 | 45 | 93.8% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 5078 | 145 | 97.1% | 2882 | 145 | 95.0% | 96.4% | 96.3% |
| `src/pystachy_compiler/flow.py` | 833 | 4 | 99.5% | 582 | 9 | 98.5% | 99.1% | 98.4% |
| `src/pystachy_compiler/functions.py` | 414 | 23 | 94.4% | 230 | 17 | 92.6% | 93.8% | 79.7% |
| `src/pystachy_compiler/gen.py` | 2846 | 2 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1048 | 37 | 96.5% | 412 | 41 | 90.0% | 94.7% | 94.7% |
| `src/pystachy_compiler/ir.py` | 430 | 3 | 99.3% | 32 | 3 | 90.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/ircheck.py` | 475 | 27 | 94.3% | 394 | 27 | 93.1% | 93.8% | 78.3% |
| `src/pystachy_compiler/lexer.py` | 636 | 26 | 95.9% | 356 | 25 | 93.0% | 94.9% | 94.9% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 3192 | 127 | 96.0% | 1996 | 137 | 93.1% | 94.9% | 94.7% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 509 | 11 | 97.8% | 274 | 7 | 97.4% | 97.7% | 55.9% |
| `src/pystachy_compiler/lowering.py` | 536 | 3 | 99.4% | 310 | 5 | 98.4% | 99.1% | 98.9% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 34 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 28 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1662 | 34 | 98.0% | 1004 | 40 | 96.0% | 97.2% | 96.7% |
| `src/pystachy_compiler/parser.py` | 2098 | 104 | 95.0% | 1170 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 235 | 15 | 93.6% | 132 | 13 | 90.2% | 92.4% | 92.4% |
| `src/pystachy_compiler/pipeline.py` | 130 | 7 | 94.6% | 52 | 8 | 84.6% | 91.8% | 85.2% |
| `src/pystachy_compiler/program.py` | 1272 | 43 | 96.6% | 944 | 47 | 95.0% | 95.9% | 95.8% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2558 | 167 | 93.5% | 1360 | 165 | 87.9% | 91.5% | 91.4% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 128 | 1 | 99.2% | 60 | 4 | 93.3% | 97.3% | 18.1% |
| `src/pystachy_compiler/specs.py` | 271 | 0 | 100.0% | 86 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1780 | 64 | 96.4% | 986 | 70 | 92.9% | 95.2% | 95.0% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 154 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 831 | 37 | 95.5% | 496 | 45 | 90.9% | 93.8% | 93.8% |
| `src/pystachy_compiler/union_arithmetic.py` | 142 | 3 | 97.9% | 56 | 3 | 94.6% | 97.0% | 97.0% |
| `src/pystachy_compiler/union_proof.py` | 851 | 13 | 98.5% | 608 | 23 | 96.2% | 97.5% | 91.8% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 465 | 22 | 95.3% | 250 | 22 | 91.2% | 93.8% | 93.8% |
| `src/pystachy_compiler/utils.py` | 775 | 26 | 96.6% | 400 | 26 | 93.5% | 95.6% | 92.2% |
| `src/pystachy_compiler/variables.py` | 1829 | 102 | 94.4% | 1144 | 110 | 90.4% | 92.9% | 92.8% |
