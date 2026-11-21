## Hosted compiler coverage

Commit `4998521d28413c6e32506105f836b6db9afeb1d7`: statements **95.6%** (58879 of 61605) and branches **92.0%** (30874 of 33570); 94.3% together, coverage.py's total. 5 suites, 9567 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 9200 passed, 0 failed | 9210 | 5707 s | 92.8% | 88.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 196 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 177 | 204 s | 46.5% | 39.0% |
| cache | `tests/cache.sh` | 99 passed, 0 failed | 53 | 328 s | 31.9% | 23.0% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 709 tests, OK | 9 | 87 s | 50.6% | 43.6% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 118 programs | 118 | 419 s | 59.7% | 53.2% |
| **all** | | | **9567** | | **95.6%** | **92.0%** |

The other suites run 1700 statements and 1061 branches that the corpus does not.

### Changed since 41dffd36201e6655c2603b28a458300c864237f7 (merge base `41dffd36201e`)

Changed statements: 1176 of 1318 run (89.2%); their branches: 623 of 738 taken (84.4%).

| File | Statements not run | Branches not taken |
|---|---|---|
| `src/pystachy_compiler/analysis.py` | 91-104 | 91->92, 91->93, 93->94, 93->95, 95->96, 95->100, 97->98, 97->100, 101->102, 101->104 |
| `src/pystachy_compiler/builtin_bases.py` | 337-338 | 336->337 |
| `src/pystachy_compiler/builtins.py` | 317-321 | 316->317, 317->318, 317->319 |
| `src/pystachy_compiler/driver.py` | 194-196, 200, 807-840, 842-845, 849, 864-866, 868, 875, 914-915, 917-923, 926-927, 929-933, 1325, 1340, 1691, 1710 | 118->exit, 191->194, 818->819, 818->842, 822->823, 822->830, 823->824, 823->830, 824->825, 824->828, 826->827, 826->828, 828->823, 828->829, 832->833, 832->834, 834->835, 834->836, 836->837, 836->839, 839->818, 839->840, 842->843, 842->844, 864->exit, 864->865, 865->866, 865->868, 874->875, 913->914, 916->917, 917->918, 917->919, 919->920, 919->922, 925->926, 928->929, 929->930, 929->931, 931->932, 931->933 |
| `src/pystachy_compiler/dynamic.py` | 254-256, 5902 | 249->254, 254->255, 254->256, 5901->5902 |
| `src/pystachy_compiler/expressions.py` | 1090-1093, 3431, 3434, 3449 | 1089->1090, 1090->1091, 1090->1092, 1092->1093, 1092->1094, 3430->3431, 3433->3434, 3448->3449 |
| `src/pystachy_compiler/functions.py` | 179, 259-263 | 178->179, 258->259, 262->263, 262->264 |
| `src/pystachy_compiler/memory_ir.py` | 42, 44 | 41->42, 43->44 |
| `src/pystachy_compiler/program.py` | 1036 | 1035->1036, 1041->1040 |
| `src/pystachy_compiler/statements.py` | 1870 | 1869->1870 |
| `src/pystachy_compiler/union_arithmetic.py` | 300, 376, 394-395, 433-434 | 299->300, 375->376, 384->388, 388->372, 390->392, 393->394, 432->433 |
| `src/pystachy_compiler/union_proof.py` | 249, 258, 266, 275, 294, 297, 328, 350, 377, 614, 893, 988 | 248->249, 257->258, 265->266, 274->275, 293->294, 296->297, 327->328, 333->337, 349->350, 370->383, 376->377, 613->614, 616->615, 892->893, 964->961, 967->964, 987->988, 1019->1023 |
| `src/pystachy_compiler/unions.py` | 134, 190, 193, 264, 274, 276, 280, 314, 316, 337, 349-350, 355 | 105->107, 133->134, 189->190, 192->193, 263->264, 273->274, 275->276, 279->280, 313->314, 315->316, 336->337, 348->349, 354->355 |
| `src/pystachy_compiler/variables.py` | 1969 | 1968->1969 |

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1731 | 85 | 95.1% | 1464 | 93 | 93.6% | 94.4% | 94.4% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 997 | 37 | 96.3% | 410 | 41 | 90.0% | 94.5% | 94.5% |
| `src/pystachy_compiler/builtin_bases.py` | 270 | 18 | 93.3% | 136 | 18 | 86.8% | 91.1% | 91.1% |
| `src/pystachy_compiler/builtins.py` | 3090 | 156 | 95.0% | 1852 | 155 | 91.6% | 93.7% | 92.8% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 231 | 59 | 74.5% | 112 | 35 | 68.8% | 72.6% | 14.9% |
| `src/pystachy_compiler/callbacks.py` | 183 | 2 | 98.9% | 92 | 3 | 96.7% | 98.2% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1540 | 53 | 96.6% | 948 | 54 | 94.3% | 95.7% | 93.7% |
| `src/pystachy_compiler/class_values.py` | 514 | 25 | 95.1% | 264 | 28 | 89.4% | 93.2% | 93.2% |
| `src/pystachy_compiler/containers.py` | 1138 | 43 | 96.2% | 622 | 43 | 93.1% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 396 | 9 | 97.7% | 246 | 7 | 97.2% | 97.5% | 97.5% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/dataflow.py` | 87 | 0 | 100.0% | 58 | 2 | 96.6% | 98.6% | 97.9% |
| `src/pystachy_compiler/declarations.py` | 2962 | 170 | 94.3% | 2012 | 173 | 91.4% | 93.1% | 92.5% |
| `src/pystachy_compiler/diagnostics.py` | 102 | 8 | 92.2% | 22 | 1 | 95.5% | 92.7% | 92.7% |
| `src/pystachy_compiler/driver.py` | 1203 | 229 | 81.0% | 522 | 163 | 68.8% | 77.3% | 62.9% |
| `src/pystachy_compiler/dynamic.py` | 4432 | 244 | 94.5% | 2304 | 262 | 88.6% | 92.5% | 92.5% |
| `src/pystachy_compiler/dynamic_proof.py` | 336 | 4 | 98.8% | 190 | 4 | 97.9% | 98.5% | 92.6% |
| `src/pystachy_compiler/emission.py` | 741 | 18 | 97.6% | 302 | 17 | 94.4% | 96.6% | 95.1% |
| `src/pystachy_compiler/exceptions.py` | 1511 | 51 | 96.6% | 734 | 46 | 93.7% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 5815 | 172 | 97.0% | 3316 | 178 | 94.6% | 96.2% | 96.1% |
| `src/pystachy_compiler/flow.py` | 850 | 4 | 99.5% | 596 | 9 | 98.5% | 99.1% | 98.5% |
| `src/pystachy_compiler/frames.py` | 129 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/functions.py` | 451 | 27 | 94.0% | 246 | 20 | 91.9% | 93.3% | 78.2% |
| `src/pystachy_compiler/gen.py` | 3215 | 3 | 99.9% | 4 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1050 | 35 | 96.7% | 412 | 39 | 90.5% | 94.9% | 94.9% |
| `src/pystachy_compiler/ir.py` | 285 | 3 | 98.9% | 102 | 3 | 97.1% | 98.4% | 94.1% |
| `src/pystachy_compiler/ircheck.py` | 813 | 31 | 96.2% | 604 | 32 | 94.7% | 95.6% | 85.9% |
| `src/pystachy_compiler/lexer.py` | 651 | 27 | 95.9% | 360 | 26 | 92.8% | 94.8% | 94.8% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 4970 | 254 | 94.9% | 3162 | 280 | 91.1% | 93.4% | 93.2% |
| `src/pystachy_compiler/local_versions.py` | 60 | 0 | 100.0% | 40 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 517 | 17 | 96.7% | 278 | 11 | 96.0% | 96.5% | 55.3% |
| `src/pystachy_compiler/lowering.py` | 547 | 2 | 99.6% | 318 | 4 | 98.7% | 99.3% | 99.0% |
| `src/pystachy_compiler/machine_ir.py` | 133 | 1 | 99.2% | 78 | 1 | 98.7% | 99.1% | 93.4% |
| `src/pystachy_compiler/memory_ir.py` | 39 | 4 | 89.7% | 18 | 4 | 77.8% | 86.0% | 71.9% |
| `src/pystachy_compiler/module.py` | 39 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 37 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1893 | 41 | 97.8% | 1106 | 50 | 95.5% | 97.0% | 96.5% |
| `src/pystachy_compiler/parser.py` | 2100 | 104 | 95.0% | 1172 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 306 | 17 | 94.4% | 166 | 16 | 90.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/pipeline.py` | 131 | 7 | 94.7% | 52 | 8 | 84.6% | 91.8% | 85.2% |
| `src/pystachy_compiler/program.py` | 1828 | 80 | 95.6% | 1350 | 90 | 93.3% | 94.7% | 94.5% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2773 | 166 | 94.0% | 1460 | 173 | 88.2% | 92.0% | 91.9% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 4 | 91.5% | 22 | 4 | 81.8% | 88.4% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 126 | 1 | 99.2% | 58 | 3 | 94.8% | 97.8% | 18.5% |
| `src/pystachy_compiler/specs.py` | 364 | 0 | 100.0% | 124 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1994 | 76 | 96.2% | 1094 | 79 | 92.8% | 95.0% | 94.9% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/symbols.py` | 166 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/syntax.py` | 155 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 851 | 34 | 96.0% | 512 | 41 | 92.0% | 94.5% | 94.5% |
| `src/pystachy_compiler/union_arithmetic.py` | 401 | 19 | 95.3% | 216 | 19 | 91.2% | 93.8% | 93.8% |
| `src/pystachy_compiler/union_proof.py` | 1094 | 27 | 97.5% | 800 | 41 | 94.9% | 96.4% | 91.8% |
| `src/pystachy_compiler/union_state.py` | 213 | 2 | 99.1% | 112 | 2 | 98.2% | 98.8% | 97.8% |
| `src/pystachy_compiler/unions.py` | 965 | 46 | 95.2% | 496 | 47 | 90.5% | 93.6% | 93.6% |
| `src/pystachy_compiler/utils.py` | 920 | 36 | 96.1% | 500 | 36 | 92.8% | 94.9% | 90.9% |
| `src/pystachy_compiler/variables.py` | 1928 | 106 | 94.5% | 1198 | 110 | 90.8% | 93.1% | 93.0% |
