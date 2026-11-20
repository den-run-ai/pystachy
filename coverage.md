## Hosted compiler coverage

Commit `41dffd36201e6655c2603b28a458300c864237f7`: statements **95.7%** (57851 of 60463) and branches **92.1%** (30293 of 32888); 94.4% together, coverage.py's total. 5 suites, 9470 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 9103 passed, 0 failed | 9113 | 5670 s | 92.9% | 88.9% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 196 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 177 | 206 s | 46.7% | 39.0% |
| cache | `tests/cache.sh` | 99 passed, 0 failed | 53 | 482 s | 32.2% | 23.2% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 691 tests, OK | 9 | 117 s | 50.5% | 43.4% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 118 programs | 118 | 304 s | 60.0% | 53.3% |
| **all** | | | **9470** | | **95.7%** | **92.1%** |

The other suites run 1691 statements and 1056 branches that the corpus does not.

### Changed since 37512410e050da72b97b927f7d69830ed8377faa (merge base `37512410e050`)

Changed statements: 3388 of 3546 run (95.5%); their branches: 1847 of 2022 taken (91.3%).

| File | Statements not run | Branches not taken |
|---|---|---|
| `src/pystachy_compiler/builtin_bases.py` | 110, 173, 175, 187-191, 216, 276, 319, 324, 331, 344, 349, 366 | 109->110, 172->173, 174->175, 185->187, 187->188, 187->189, 189->190, 189->191, 194->exit, 214->216, 275->276, 318->319, 323->324, 330->331, 343->344, 348->349, 365->366 |
| `src/pystachy_compiler/builtins.py` | - | 1669->1671 |
| `src/pystachy_compiler/calls.py` | 908 | 906->908 |
| `src/pystachy_compiler/conversions.py` | 342 | 340->342 |
| `src/pystachy_compiler/declarations.py` | 2927-2928 | 2840->2845, 2927->2928, 2927->2929 |
| `src/pystachy_compiler/dynamic.py` | 1368, 1400 | 1367->1368, 1399->1400 |
| `src/pystachy_compiler/emission.py` | 247, 255, 415, 486 | 246->247, 254->255, 414->415, 482->469, 485->486 |
| `src/pystachy_compiler/exceptions.py` | 1434 | 1433->1434 |
| `src/pystachy_compiler/expressions.py` | 676, 681, 697, 702, 707, 727, 756-758, 763, 6293 | 675->676, 677->681, 694->696, 696->697, 701->702, 706->707, 726->727, 755->756, 756->757, 756->758, 762->763, 5822->5826 |
| `src/pystachy_compiler/functions.py` | 311, 317 | - |
| `src/pystachy_compiler/ircheck.py` | 299-300, 420, 460-461, 735, 792, 794, 796, 798, 817, 821, 823 | 292->299, 401->404, 419->420, 459->460, 460->459, 460->461, 731->735, 791->792, 793->794, 795->796, 797->798, 816->817, 820->821, 822->823, 908->909, 917->918 |
| `src/pystachy_compiler/loader.py` | 557-559, 566, 568, 573, 576, 583, 586, 631, 634, 636, 639, 642, 646, 664, 667, 673, 678, 680, 687, 732-733, 748, 860-862, 879, 890, 893, 920-921, 927, 945-948, 1005, 1048, 1050-1051, 1055, 1271, 1359-1360, 1372, 1374-1377, 1552, 1555-1562, 1585, 1589, 1604-1605, 1607, 1614, 1635, 1637, 1639, 1642, 1687, 1767, 1790, 1845, 1850, 1853, 1889, 1893, 1908, 2010, 2170-2171, 2173, 2203, 2810, 2812, 6017 | 555->557, 557->558, 557->559, 565->566, 567->568, 572->573, 575->576, 582->583, 585->586, 598->597, 630->631, 633->634, 635->636, 638->639, 641->642, 645->646, 663->664, 666->667, 668->665, 672->673, 677->678, 679->680, 686->687, 731->732, 732->731, 732->733, 735->734, 747->748, 859->860, 861->859, 861->862, 878->879, 889->890, 891->893, 916->920, 920->exit, 920->921, 926->927, 944->945, 945->946, 945->948, 946->945, 946->947, 1004->1005, 1047->1048, 1049->1050, 1054->1055, 1270->1271, 1358->1359, 1371->1372, 1373->1374, 1375->1376, 1375->1377, 1551->1552, 1553->1555, 1555->1556, 1555->1557, 1557->1558, 1557->1562, 1559->1560, 1559->1561, 1584->1585, 1588->1589, 1602->1604, 1604->1605, 1604->1607, 1613->1614, 1631->1635, 1636->1637, 1638->1639, 1641->1642, 1686->1687, 1789->1790, 1844->1845, 1849->1850, 1852->1853, 1888->1889, 1892->1893, 1899->1901, 1907->1908, 1914->1909, 1915->1914, 2009->2010, 2169->2170, 2172->2173, 2202->2203, 2809->2810, 2811->2812, 6016->6017 |
| `src/pystachy_compiler/machine_ir.py` | 82 | 81->82 |
| `src/pystachy_compiler/optimizations.py` | 1015, 1695 | 1014->1015, 1563->1546, 1694->1695, 1707->1709 |
| `src/pystachy_compiler/program.py` | 537 | 534->537, 699->698 |
| `src/pystachy_compiler/reflection.py` | 128, 227, 241-242, 3603 | 127->128, 226->227, 240->241, 256->260, 893->896, 957->961 |
| `src/pystachy_compiler/statements.py` | 1481 | 1480->1481, 1610->1612 |
| `src/pystachy_compiler/union_proof.py` | 781 | 488->490, 780->781 |
| `src/pystachy_compiler/unions.py` | - | 936->937, 940->942 |
| `src/pystachy_compiler/utils.py` | 238-240, 251, 259, 263, 271, 300 | 237->238, 238->239, 238->240, 250->251, 258->259, 262->263, 270->271, 299->300 |

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1716 | 70 | 95.9% | 1454 | 82 | 94.4% | 95.2% | 95.1% |
| `src/pystachy_compiler/aot_runtime.py` | 132 | 15 | 88.6% | 66 | 12 | 81.8% | 86.4% | 86.4% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 997 | 37 | 96.3% | 410 | 41 | 90.0% | 94.5% | 94.5% |
| `src/pystachy_compiler/builtin_bases.py` | 257 | 16 | 93.8% | 130 | 17 | 86.9% | 91.5% | 91.5% |
| `src/pystachy_compiler/builtins.py` | 3080 | 151 | 95.1% | 1844 | 152 | 91.8% | 93.8% | 92.9% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 226 | 59 | 73.9% | 110 | 35 | 68.2% | 72.0% | 13.7% |
| `src/pystachy_compiler/callbacks.py` | 183 | 2 | 98.9% | 92 | 3 | 96.7% | 98.2% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1538 | 53 | 96.6% | 946 | 53 | 94.4% | 95.7% | 94.0% |
| `src/pystachy_compiler/class_values.py` | 512 | 25 | 95.1% | 264 | 28 | 89.4% | 93.2% | 93.2% |
| `src/pystachy_compiler/containers.py` | 1138 | 43 | 96.2% | 622 | 43 | 93.1% | 95.1% | 95.1% |
| `src/pystachy_compiler/conversions.py` | 396 | 11 | 97.2% | 246 | 9 | 96.3% | 96.9% | 96.9% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/dataflow.py` | 86 | 0 | 100.0% | 58 | 2 | 96.6% | 98.6% | 97.9% |
| `src/pystachy_compiler/declarations.py` | 2962 | 170 | 94.3% | 2012 | 173 | 91.4% | 93.1% | 92.5% |
| `src/pystachy_compiler/diagnostics.py` | 97 | 8 | 91.8% | 22 | 1 | 95.5% | 92.4% | 92.4% |
| `src/pystachy_compiler/driver.py` | 1124 | 173 | 84.6% | 474 | 123 | 74.1% | 81.5% | 66.0% |
| `src/pystachy_compiler/dynamic.py` | 4411 | 248 | 94.4% | 2290 | 266 | 88.4% | 92.3% | 92.3% |
| `src/pystachy_compiler/dynamic_proof.py` | 336 | 4 | 98.8% | 190 | 4 | 97.9% | 98.5% | 92.6% |
| `src/pystachy_compiler/emission.py` | 705 | 19 | 97.3% | 280 | 18 | 93.6% | 96.2% | 94.6% |
| `src/pystachy_compiler/exceptions.py` | 1511 | 51 | 96.6% | 734 | 46 | 93.7% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 5737 | 169 | 97.1% | 3272 | 172 | 94.7% | 96.2% | 96.2% |
| `src/pystachy_compiler/flow.py` | 850 | 4 | 99.5% | 596 | 9 | 98.5% | 99.1% | 98.5% |
| `src/pystachy_compiler/frames.py` | 129 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/functions.py` | 441 | 21 | 95.2% | 240 | 16 | 93.3% | 94.6% | 79.1% |
| `src/pystachy_compiler/gen.py` | 3176 | 3 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1050 | 35 | 96.7% | 412 | 39 | 90.5% | 94.9% | 94.9% |
| `src/pystachy_compiler/ir.py` | 285 | 3 | 98.9% | 102 | 3 | 97.1% | 98.4% | 94.1% |
| `src/pystachy_compiler/ircheck.py` | 778 | 33 | 95.8% | 572 | 34 | 94.1% | 95.0% | 85.0% |
| `src/pystachy_compiler/lexer.py` | 651 | 27 | 95.9% | 360 | 26 | 92.8% | 94.8% | 94.8% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 4965 | 254 | 94.9% | 3158 | 280 | 91.1% | 93.4% | 93.2% |
| `src/pystachy_compiler/local_versions.py` | 60 | 0 | 100.0% | 40 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 517 | 17 | 96.7% | 278 | 11 | 96.0% | 96.5% | 55.3% |
| `src/pystachy_compiler/lowering.py` | 530 | 2 | 99.6% | 302 | 4 | 98.7% | 99.3% | 98.9% |
| `src/pystachy_compiler/machine_ir.py` | 133 | 1 | 99.2% | 78 | 1 | 98.7% | 99.1% | 93.4% |
| `src/pystachy_compiler/memory_ir.py` | 35 | 2 | 94.3% | 14 | 2 | 85.7% | 91.8% | 75.5% |
| `src/pystachy_compiler/module.py` | 39 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 37 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1893 | 41 | 97.8% | 1106 | 50 | 95.5% | 97.0% | 96.5% |
| `src/pystachy_compiler/parser.py` | 2100 | 104 | 95.0% | 1172 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 306 | 17 | 94.4% | 166 | 16 | 90.4% | 93.0% | 93.0% |
| `src/pystachy_compiler/pipeline.py` | 130 | 7 | 94.6% | 52 | 8 | 84.6% | 91.8% | 85.2% |
| `src/pystachy_compiler/program.py` | 1814 | 79 | 95.6% | 1340 | 88 | 93.4% | 94.7% | 94.5% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2773 | 166 | 94.0% | 1460 | 173 | 88.2% | 92.0% | 91.9% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 4 | 91.5% | 22 | 4 | 81.8% | 88.4% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 126 | 1 | 99.2% | 58 | 3 | 94.8% | 97.8% | 18.5% |
| `src/pystachy_compiler/specs.py` | 360 | 0 | 100.0% | 124 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1963 | 75 | 96.2% | 1080 | 78 | 92.8% | 95.0% | 94.9% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/symbols.py` | 165 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/syntax.py` | 155 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 851 | 34 | 96.0% | 512 | 41 | 92.0% | 94.5% | 94.5% |
| `src/pystachy_compiler/union_arithmetic.py` | 224 | 13 | 94.2% | 124 | 12 | 90.3% | 92.8% | 92.8% |
| `src/pystachy_compiler/union_proof.py` | 807 | 16 | 98.0% | 574 | 24 | 95.8% | 97.1% | 91.6% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 765 | 32 | 95.8% | 404 | 33 | 91.8% | 94.4% | 94.4% |
| `src/pystachy_compiler/utils.py` | 909 | 36 | 96.0% | 490 | 36 | 92.7% | 94.9% | 90.8% |
| `src/pystachy_compiler/variables.py` | 1892 | 105 | 94.5% | 1180 | 109 | 90.8% | 93.0% | 92.9% |
