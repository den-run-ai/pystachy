## Hosted compiler coverage

Commit `3cf23d20357be84bf731090112cdb89df0749cb4`: statements **95.7%** (51091 of 53402) and branches **92.2%** (26607 of 28862); 94.4% together, coverage.py's total. 5 suites, 8274 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 7924 passed, 0 failed | 7934 | 4962 s | 92.6% | 88.7% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 194 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 175 | 192 s | 48.2% | 40.8% |
| cache | `tests/cache.sh` | 98 passed, 0 failed | 52 | 286 s | 33.1% | 24.2% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 551 tests, OK | 9 | 67 s | 51.4% | 44.4% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 104 programs | 104 | 173 s | 59.0% | 52.5% |
| **all** | | | **8274** | | **95.7%** | **92.2%** |

The other suites run 1659 statements and 1019 branches that the corpus does not.

### Changed since d58034c1ca588c90363b8deb3b3c633b1cc90c47 (merge base `d58034c1ca58`)

Changed statements: 844 of 939 run (89.9%); their branches: 457 of 554 taken (82.5%).

| File | Statements not run | Branches not taken |
|---|---|---|
| `src/pystachy_compiler/declarations.py` | 385, 2378, 2399, 2412, 2721, 2742, 2754-2755, 2780, 2861-2867, 2869-2872, 2877-2885, 2896 | 384->385, 2377->2378, 2398->2399, 2411->2412, 2420->exit, 2591->2588, 2595->2597, 2720->2721, 2724->2728, 2741->2742, 2753->2754, 2779->2780, 2863->2864, 2863->2870, 2864->2865, 2864->2869, 2865->2866, 2865->2867, 2870->2871, 2870->2872, 2877->2878, 2877->2879, 2879->2880, 2879->2885, 2880->2879, 2880->2881, 2882->2879, 2882->2883, 2883->2882, 2883->2884, 2892->2896 |
| `src/pystachy_compiler/dynamic.py` | 4249, 4251, 4267, 4269, 4271, 4297-4298, 4313-4314, 4316, 4318, 4341, 4356-4357, 4359-4366, 4368-4369, 4415-4416, 4418, 4426 | 4248->4249, 4250->4251, 4266->4267, 4268->4269, 4270->4271, 4296->4297, 4311->4313, 4313->4314, 4313->4316, 4317->4318, 4340->4341, 4347->4346, 4355->4356, 4363->4364, 4363->4369, 4364->4365, 4364->4368, 4365->4366, 4365->4369, 4413->4415, 4415->4416, 4415->4418, 4425->4426 |
| `src/pystachy_compiler/emission.py` | 37 | 34->37, 49->53 |
| `src/pystachy_compiler/expressions.py` | 149, 161, 4346 | 148->149, 150->147, 158->161, 4326->4331, 4345->4346, 4359->4358 |
| `src/pystachy_compiler/gen.py` | 3187 | - |
| `src/pystachy_compiler/lexer.py` | 33 | 32->33 |
| `src/pystachy_compiler/loader.py` | 120, 190, 193, 196, 199, 201-203, 327, 2364, 2378, 2380, 2388, 2391-2393, 2395, 3973 | 119->120, 189->190, 192->193, 195->196, 198->199, 200->201, 202->203, 202->204, 222->224, 326->327, 2363->2364, 2377->2378, 2379->2380, 2387->2388, 2390->2391, 2391->2392, 2391->2393, 2394->2395, 3970->3973, 4113->4111 |
| `src/pystachy_compiler/patterns.py` | 321-326, 359, 361 | 318->321, 321->322, 321->323, 323->324, 323->325, 325->326, 325->327, 356->357, 358->359, 360->361 |
| `src/pystachy_compiler/templates.py` | 460 | 459->460 |
| `src/pystachy_compiler/variables.py` | 668, 881, 1216, 1691 | 664->668, 1213->1216, 1687->1691 |

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1602 | 72 | 95.5% | 1360 | 85 | 93.8% | 94.7% | 94.6% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 996 | 38 | 96.2% | 410 | 42 | 89.8% | 94.3% | 94.3% |
| `src/pystachy_compiler/builtins.py` | 2852 | 137 | 95.2% | 1712 | 135 | 92.1% | 94.0% | 93.1% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 226 | 59 | 73.9% | 110 | 35 | 68.2% | 72.0% | 13.7% |
| `src/pystachy_compiler/callbacks.py` | 180 | 2 | 98.9% | 90 | 3 | 96.7% | 98.1% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1467 | 51 | 96.5% | 890 | 50 | 94.4% | 95.7% | 93.8% |
| `src/pystachy_compiler/containers.py` | 1057 | 40 | 96.2% | 576 | 40 | 93.1% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 315 | 10 | 96.8% | 204 | 8 | 96.1% | 96.5% | 96.5% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/declarations.py` | 2680 | 169 | 93.7% | 1822 | 163 | 91.1% | 92.6% | 92.0% |
| `src/pystachy_compiler/diagnostics.py` | 93 | 8 | 91.4% | 22 | 1 | 95.5% | 92.2% | 92.2% |
| `src/pystachy_compiler/driver.py` | 1086 | 166 | 84.7% | 456 | 116 | 74.6% | 81.7% | 65.6% |
| `src/pystachy_compiler/dynamic.py` | 4214 | 253 | 94.0% | 2206 | 271 | 87.7% | 91.8% | 91.8% |
| `src/pystachy_compiler/dynamic_proof.py` | 409 | 4 | 99.0% | 248 | 7 | 97.2% | 98.3% | 93.2% |
| `src/pystachy_compiler/emission.py` | 562 | 17 | 97.0% | 190 | 15 | 92.1% | 95.7% | 93.9% |
| `src/pystachy_compiler/exceptions.py` | 1499 | 50 | 96.7% | 726 | 45 | 93.8% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 5144 | 148 | 97.1% | 2922 | 151 | 94.8% | 96.3% | 96.3% |
| `src/pystachy_compiler/flow.py` | 833 | 4 | 99.5% | 582 | 9 | 98.5% | 99.1% | 98.4% |
| `src/pystachy_compiler/functions.py` | 416 | 23 | 94.5% | 230 | 17 | 92.6% | 93.8% | 79.7% |
| `src/pystachy_compiler/gen.py` | 2862 | 3 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1048 | 37 | 96.5% | 412 | 41 | 90.0% | 94.7% | 94.7% |
| `src/pystachy_compiler/ir.py` | 430 | 3 | 99.3% | 32 | 3 | 90.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/ircheck.py` | 475 | 27 | 94.3% | 394 | 27 | 93.1% | 93.8% | 78.3% |
| `src/pystachy_compiler/lexer.py` | 644 | 27 | 95.8% | 360 | 26 | 92.8% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 3321 | 135 | 95.9% | 2054 | 146 | 92.9% | 94.8% | 94.6% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 509 | 11 | 97.8% | 274 | 7 | 97.4% | 97.7% | 55.9% |
| `src/pystachy_compiler/lowering.py` | 536 | 3 | 99.4% | 310 | 5 | 98.4% | 99.1% | 98.9% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 34 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 28 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1662 | 34 | 98.0% | 1004 | 40 | 96.0% | 97.2% | 96.7% |
| `src/pystachy_compiler/parser.py` | 2098 | 104 | 95.0% | 1170 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 306 | 17 | 94.4% | 166 | 16 | 90.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/pipeline.py` | 130 | 7 | 94.6% | 52 | 8 | 84.6% | 91.8% | 85.2% |
| `src/pystachy_compiler/program.py` | 1272 | 43 | 96.6% | 944 | 47 | 95.0% | 95.9% | 95.8% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2558 | 167 | 93.5% | 1360 | 165 | 87.9% | 91.5% | 91.4% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 126 | 1 | 99.2% | 58 | 3 | 94.8% | 97.8% | 18.5% |
| `src/pystachy_compiler/specs.py` | 271 | 0 | 100.0% | 86 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1780 | 64 | 96.4% | 986 | 70 | 92.9% | 95.2% | 95.0% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 154 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 831 | 37 | 95.5% | 496 | 45 | 90.9% | 93.8% | 93.8% |
| `src/pystachy_compiler/union_arithmetic.py` | 142 | 3 | 97.9% | 56 | 3 | 94.6% | 97.0% | 97.0% |
| `src/pystachy_compiler/union_proof.py` | 851 | 13 | 98.5% | 608 | 23 | 96.2% | 97.5% | 91.9% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 491 | 22 | 95.5% | 260 | 22 | 91.5% | 94.1% | 94.1% |
| `src/pystachy_compiler/utils.py` | 775 | 26 | 96.6% | 400 | 26 | 93.5% | 95.6% | 92.2% |
| `src/pystachy_compiler/variables.py` | 1835 | 105 | 94.3% | 1150 | 112 | 90.3% | 92.7% | 92.7% |
