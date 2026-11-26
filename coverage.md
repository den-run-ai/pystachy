## Hosted compiler coverage

Commit `4799a9bc58657d1040b19718d04753620a4d6f73`: statements **95.5%** (61114 of 63961) and branches **91.9%** (32169 of 35008); 94.3% together, coverage.py's total. 5 suites, 9952 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 9585 passed, 0 failed | 9595 | 6414 s | 93.0% | 89.0% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 196 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 177 | 250 s | 45.9% | 38.4% |
| cache | `tests/cache.sh` | 99 passed, 0 failed | 53 | 337 s | 31.5% | 22.5% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 716 tests, OK | 9 | 101 s | 51.0% | 44.0% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 118 programs | 118 | 336 s | 59.4% | 53.0% |
| **all** | | | **9952** | | **95.5%** | **91.9%** |

The other suites run 1624 statements and 1022 branches that the corpus does not.

### Changed since a130cf51cb1a207c7852c44e651bbf931286e246 (merge base `a130cf51cb1a`)

Changed statements: 881 of 918 run (96.0%); their branches: 475 of 532 taken (89.3%).

| File | Statements not run | Branches not taken |
|---|---|---|
| `src/pystachy_compiler/builtin_bases.py` | 175, 190, 199, 264, 382-384 | 174->175, 189->190, 198->199, 243->249, 263->264, 268->273, 380->382, 383->368, 383->384 |
| `src/pystachy_compiler/calls.py` | 759, 763 | 436->438, 756->755, 758->759, 762->763 |
| `src/pystachy_compiler/class_values.py` | - | 614->619 |
| `src/pystachy_compiler/driver.py` | - | 261->262 |
| `src/pystachy_compiler/dynamic.py` | 5474, 5483 | 5473->5474, 5482->5483 |
| `src/pystachy_compiler/expressions.py` | 1794, 5010 | 1793->1794, 2008->1998, 2025->2029, 5009->5010, 5193->5197 |
| `src/pystachy_compiler/statements.py` | - | 318->320, 448->450, 847->857 |
| `src/pystachy_compiler/templates.py` | 341, 354, 392, 410, 426-427 | 340->341, 353->354, 359->356, 365->356, 391->392, 409->410, 425->426 |
| `src/pystachy_compiler/variables.py` | 1261, 1264, 1270, 1275, 1284, 1291, 1295, 1300, 1312, 1336, 1340, 1344, 1358, 1385, 1412, 1416, 2365, 2421 | 425->427, 1260->1261, 1263->1264, 1269->1270, 1274->1275, 1283->1284, 1290->1291, 1292->1294, 1294->1295, 1299->1300, 1307->1309, 1309->1312, 1310->1312, 1335->1336, 1339->1340, 1343->1344, 1357->1358, 1383->1385, 1411->1412, 1415->1416, 1466->1470, 2181->2183, 2314->exit, 2364->2365, 2420->2421 |

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1731 | 85 | 95.1% | 1464 | 93 | 93.6% | 94.4% | 94.4% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 997 | 37 | 96.3% | 410 | 41 | 90.0% | 94.5% | 94.5% |
| `src/pystachy_compiler/builtin_bases.py` | 424 | 25 | 94.1% | 222 | 27 | 87.8% | 92.0% | 92.0% |
| `src/pystachy_compiler/builtins.py` | 3097 | 156 | 95.0% | 1858 | 155 | 91.7% | 93.7% | 92.8% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 231 | 59 | 74.5% | 112 | 35 | 68.8% | 72.6% | 14.9% |
| `src/pystachy_compiler/callbacks.py` | 183 | 2 | 98.9% | 92 | 3 | 96.7% | 98.2% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1633 | 55 | 96.6% | 1004 | 58 | 94.2% | 95.7% | 93.9% |
| `src/pystachy_compiler/class_proof.py` | 470 | 35 | 92.6% | 310 | 33 | 89.4% | 91.3% | 89.1% |
| `src/pystachy_compiler/class_values.py` | 546 | 25 | 95.4% | 280 | 29 | 89.6% | 93.5% | 93.5% |
| `src/pystachy_compiler/containers.py` | 1138 | 43 | 96.2% | 622 | 43 | 93.1% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 404 | 9 | 97.8% | 252 | 7 | 97.2% | 97.6% | 97.6% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/dataflow.py` | 89 | 0 | 100.0% | 56 | 2 | 96.4% | 98.6% | 97.9% |
| `src/pystachy_compiler/declarations.py` | 3066 | 174 | 94.3% | 2080 | 178 | 91.4% | 93.2% | 92.6% |
| `src/pystachy_compiler/diagnostics.py` | 102 | 8 | 92.2% | 22 | 1 | 95.5% | 92.7% | 92.7% |
| `src/pystachy_compiler/driver.py` | 1242 | 243 | 80.4% | 542 | 175 | 67.7% | 76.6% | 62.7% |
| `src/pystachy_compiler/dynamic.py` | 4437 | 246 | 94.5% | 2308 | 264 | 88.6% | 92.4% | 92.4% |
| `src/pystachy_compiler/dynamic_proof.py` | 338 | 5 | 98.5% | 190 | 4 | 97.9% | 98.3% | 92.4% |
| `src/pystachy_compiler/emission.py` | 745 | 19 | 97.4% | 306 | 18 | 94.1% | 96.5% | 95.0% |
| `src/pystachy_compiler/exceptions.py` | 1511 | 51 | 96.6% | 734 | 46 | 93.7% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 5971 | 172 | 97.1% | 3402 | 181 | 94.7% | 96.2% | 96.2% |
| `src/pystachy_compiler/flow.py` | 852 | 4 | 99.5% | 598 | 9 | 98.5% | 99.1% | 98.5% |
| `src/pystachy_compiler/frames.py` | 129 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/functions.py` | 447 | 27 | 94.0% | 238 | 20 | 91.6% | 93.1% | 79.9% |
| `src/pystachy_compiler/gen.py` | 3288 | 3 | 99.9% | 4 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1050 | 35 | 96.7% | 412 | 39 | 90.5% | 94.9% | 94.9% |
| `src/pystachy_compiler/ir.py` | 285 | 3 | 98.9% | 102 | 3 | 97.1% | 98.4% | 95.3% |
| `src/pystachy_compiler/ircheck.py` | 900 | 31 | 96.6% | 672 | 32 | 95.2% | 96.0% | 86.3% |
| `src/pystachy_compiler/lexer.py` | 651 | 27 | 95.9% | 360 | 26 | 92.8% | 94.8% | 94.8% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 5039 | 261 | 94.8% | 3214 | 287 | 91.1% | 93.4% | 93.2% |
| `src/pystachy_compiler/local_versions.py` | 60 | 0 | 100.0% | 40 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 518 | 17 | 96.7% | 278 | 11 | 96.0% | 96.5% | 55.4% |
| `src/pystachy_compiler/lowering.py` | 552 | 2 | 99.6% | 322 | 4 | 98.8% | 99.3% | 99.0% |
| `src/pystachy_compiler/machine_ir.py` | 133 | 1 | 99.2% | 78 | 1 | 98.7% | 99.1% | 93.4% |
| `src/pystachy_compiler/memory_ir.py` | 42 | 5 | 88.1% | 20 | 5 | 75.0% | 83.9% | 71.0% |
| `src/pystachy_compiler/module.py` | 39 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 37 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1890 | 41 | 97.8% | 1104 | 50 | 95.5% | 97.0% | 96.5% |
| `src/pystachy_compiler/parser.py` | 2100 | 104 | 95.0% | 1172 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 306 | 17 | 94.4% | 166 | 16 | 90.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/pipeline.py` | 131 | 7 | 94.7% | 52 | 8 | 84.6% | 91.8% | 85.2% |
| `src/pystachy_compiler/program.py` | 2097 | 100 | 95.2% | 1522 | 112 | 92.6% | 94.1% | 94.0% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2777 | 167 | 94.0% | 1460 | 174 | 88.1% | 92.0% | 91.9% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 4 | 91.5% | 22 | 4 | 81.8% | 88.4% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 130 | 1 | 99.2% | 58 | 2 | 96.6% | 98.4% | 90.4% |
| `src/pystachy_compiler/specs.py` | 365 | 0 | 100.0% | 124 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 2043 | 75 | 96.3% | 1130 | 81 | 92.8% | 95.1% | 95.0% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/structure.py` | 112 | 0 | 100.0% | 70 | 2 | 97.1% | 98.9% | 97.8% |
| `src/pystachy_compiler/symbols.py` | 171 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/syntax.py` | 155 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 1107 | 48 | 95.7% | 664 | 57 | 91.4% | 94.1% | 94.1% |
| `src/pystachy_compiler/union_arithmetic.py` | 401 | 19 | 95.3% | 216 | 19 | 91.2% | 93.8% | 93.8% |
| `src/pystachy_compiler/union_proof.py` | 1107 | 28 | 97.5% | 806 | 41 | 94.9% | 96.4% | 91.7% |
| `src/pystachy_compiler/union_state.py` | 287 | 2 | 99.3% | 168 | 2 | 98.8% | 99.1% | 99.1% |
| `src/pystachy_compiler/unions.py` | 991 | 44 | 95.6% | 514 | 46 | 91.1% | 94.0% | 94.0% |
| `src/pystachy_compiler/utils.py` | 920 | 36 | 96.1% | 500 | 36 | 92.8% | 94.9% | 90.9% |
| `src/pystachy_compiler/variables.py` | 2162 | 120 | 94.4% | 1348 | 134 | 90.1% | 92.8% | 92.6% |
