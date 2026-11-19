## Hosted compiler coverage

Commit `d35417c967f25ac699bb713f4c796dfaf2c57fac`: statements **95.7%** (55152 of 57642) and branches **92.1%** (28708 of 31156); 94.4% together, coverage.py's total. 5 suites, 9136 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 8784 passed, 0 failed | 8794 | 4890 s | 92.8% | 88.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 194 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 175 | 251 s | 46.8% | 39.2% |
| cache | `tests/cache.sh` | 99 passed, 0 failed | 53 | 319 s | 32.3% | 23.3% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 618 tests, OK | 9 | 73 s | 50.3% | 43.3% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 105 programs | 105 | 337 s | 57.4% | 50.6% |
| **all** | | | **9136** | | **95.7%** | **92.1%** |

The other suites run 1670 statements and 1032 branches that the corpus does not.

### Changed since 8259611ec88d5aa6af82d0098afb9dd621eb5617 (merge base `8259611ec88d`)

Changed statements: 62 of 73 run (84.9%); their branches: 28 of 34 taken (82.4%).

| File | Statements not run | Branches not taken |
|---|---|---|
| `src/pystachy_compiler/statements.py` | 1672, 1689, 1692-1700 | 1670->1662, 1671->1672, 1688->1689, 1691->1692, 1693->1694, 1693->1695 |

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1716 | 70 | 95.9% | 1454 | 82 | 94.4% | 95.2% | 95.1% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 997 | 37 | 96.3% | 410 | 41 | 90.0% | 94.5% | 94.5% |
| `src/pystachy_compiler/builtins.py` | 3072 | 151 | 95.1% | 1838 | 151 | 91.8% | 93.8% | 92.9% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 226 | 59 | 73.9% | 110 | 35 | 68.2% | 72.0% | 13.7% |
| `src/pystachy_compiler/callbacks.py` | 181 | 2 | 98.9% | 90 | 3 | 96.7% | 98.2% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1512 | 52 | 96.6% | 926 | 52 | 94.4% | 95.7% | 93.9% |
| `src/pystachy_compiler/class_values.py` | 512 | 26 | 94.9% | 264 | 28 | 89.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/containers.py` | 1123 | 43 | 96.2% | 616 | 43 | 93.0% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 369 | 10 | 97.3% | 232 | 8 | 96.6% | 97.0% | 97.0% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/dataflow.py` | 86 | 0 | 100.0% | 58 | 2 | 96.6% | 98.6% | 97.9% |
| `src/pystachy_compiler/declarations.py` | 2917 | 176 | 94.0% | 1980 | 175 | 91.2% | 92.8% | 92.3% |
| `src/pystachy_compiler/diagnostics.py` | 95 | 8 | 91.6% | 22 | 1 | 95.5% | 92.3% | 92.3% |
| `src/pystachy_compiler/driver.py` | 1118 | 173 | 84.5% | 472 | 123 | 73.9% | 81.4% | 65.8% |
| `src/pystachy_compiler/dynamic.py` | 4269 | 252 | 94.1% | 2224 | 270 | 87.9% | 92.0% | 92.0% |
| `src/pystachy_compiler/dynamic_proof.py` | 336 | 4 | 98.8% | 190 | 4 | 97.9% | 98.5% | 92.0% |
| `src/pystachy_compiler/emission.py` | 591 | 16 | 97.3% | 194 | 14 | 92.8% | 96.2% | 94.4% |
| `src/pystachy_compiler/exceptions.py` | 1506 | 50 | 96.7% | 730 | 45 | 93.8% | 95.8% | 95.8% |
| `src/pystachy_compiler/expressions.py` | 5581 | 161 | 97.1% | 3156 | 162 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/flow.py` | 833 | 4 | 99.5% | 582 | 9 | 98.5% | 99.1% | 98.4% |
| `src/pystachy_compiler/frames.py` | 129 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/functions.py` | 425 | 21 | 95.1% | 230 | 16 | 93.0% | 94.4% | 80.5% |
| `src/pystachy_compiler/gen.py` | 3108 | 3 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1050 | 35 | 96.7% | 412 | 39 | 90.5% | 94.9% | 94.9% |
| `src/pystachy_compiler/ir.py` | 256 | 5 | 98.0% | 80 | 5 | 93.8% | 97.0% | 92.3% |
| `src/pystachy_compiler/ircheck.py` | 486 | 31 | 93.6% | 396 | 31 | 92.2% | 93.0% | 78.3% |
| `src/pystachy_compiler/lexer.py` | 651 | 27 | 95.9% | 360 | 26 | 92.8% | 94.8% | 94.8% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 4059 | 173 | 95.7% | 2512 | 194 | 92.3% | 94.4% | 94.3% |
| `src/pystachy_compiler/local_versions.py` | 60 | 0 | 100.0% | 40 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 517 | 17 | 96.7% | 278 | 11 | 96.0% | 96.5% | 55.3% |
| `src/pystachy_compiler/lowering.py` | 529 | 2 | 99.6% | 302 | 4 | 98.7% | 99.3% | 98.9% |
| `src/pystachy_compiler/machine_ir.py` | 44 | 0 | 100.0% | 24 | 0 | 100.0% | 100.0% | 92.6% |
| `src/pystachy_compiler/memory_ir.py` | 34 | 0 | 100.0% | 14 | 0 | 100.0% | 100.0% | 75.0% |
| `src/pystachy_compiler/module.py` | 39 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 29 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1835 | 39 | 97.9% | 1078 | 46 | 95.7% | 97.1% | 96.6% |
| `src/pystachy_compiler/parser.py` | 2098 | 104 | 95.0% | 1170 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 306 | 17 | 94.4% | 166 | 16 | 90.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/pipeline.py` | 130 | 7 | 94.6% | 52 | 8 | 84.6% | 91.8% | 85.2% |
| `src/pystachy_compiler/program.py` | 1778 | 77 | 95.7% | 1304 | 85 | 93.5% | 94.7% | 94.6% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2593 | 164 | 93.7% | 1382 | 168 | 87.8% | 91.6% | 91.5% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 126 | 1 | 99.2% | 58 | 3 | 94.8% | 97.8% | 18.5% |
| `src/pystachy_compiler/specs.py` | 313 | 0 | 100.0% | 96 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1920 | 75 | 96.1% | 1054 | 77 | 92.7% | 94.9% | 94.8% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/symbols.py` | 144 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/syntax.py` | 154 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 846 | 34 | 96.0% | 508 | 41 | 91.9% | 94.5% | 94.5% |
| `src/pystachy_compiler/union_arithmetic.py` | 222 | 14 | 93.7% | 124 | 13 | 89.5% | 92.2% | 92.2% |
| `src/pystachy_compiler/union_proof.py` | 794 | 13 | 98.4% | 562 | 20 | 96.4% | 97.6% | 92.0% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 721 | 31 | 95.7% | 390 | 32 | 91.8% | 94.3% | 94.3% |
| `src/pystachy_compiler/utils.py` | 790 | 28 | 96.5% | 404 | 28 | 93.1% | 95.3% | 92.0% |
| `src/pystachy_compiler/variables.py` | 1874 | 107 | 94.3% | 1168 | 110 | 90.6% | 92.9% | 92.8% |
