## Hosted compiler coverage

Commit `f5a09d4223139d7255e31051be97fc509e1ca1fe`: statements **95.9%** (36111 of 37640) and branches **92.6%** (19099 of 20618); 94.8% together, coverage.py's total. 5 suites, 5686 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 5438 passed, 0 failed | 5446 | 2764 s | 94.7% | 91.0% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 139 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 126 | 127 s | 37.9% | 29.7% |
| cache | `tests/cache.sh` | 67 passed, 0 failed | 33 | 228 s | 29.7% | 20.3% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 140 tests, OK | 2 | 14 s | 50.6% | 43.2% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 79 programs | 79 | 128 s | 59.1% | 52.0% |
| **all** | | | **5686** | | **95.9%** | **92.6%** |

The other suites run 468 statements and 344 branches that the corpus does not.

### Changed since v0.1.0-alpha.2 (merge base `afb59cd3c32e`)

Changed statements: 3236 of 3330 run (97.2%); their branches: 1763 of 1876 taken (94.0%).

| File | Statements not run | Branches not taken |
|---|---|---|
| `src/pystachy_compiler/analysis.py` | 58 | 57->58 |
| `src/pystachy_compiler/builtins.py` | 899 | 1422->1423 |
| `src/pystachy_compiler/calls.py` | 232, 236, 238, 764 | 206->208, 231->232, 235->236, 237->238, 241->243 |
| `src/pystachy_compiler/containers.py` | 567 | 566->567, 568->571 |
| `src/pystachy_compiler/declarations.py` | 217, 294-295 | 216->217, 293->294 |
| `src/pystachy_compiler/driver.py` | 134, 145, 147, 316, 603-604 | 133->134, 144->145, 146->147, 600->603 |
| `src/pystachy_compiler/dynamic.py` | 182, 202, 216, 259, 545, 733, 742, 746, 758, 1400, 1472, 1490, 1593-1594, 1645-1646, 1763, 1767, 1769, 1957, 2130, 2213, 2221, 2230, 2235 | 178->182, 201->202, 215->216, 258->259, 266->268, 275->277, 306->317, 359->368, 544->545, 732->733, 741->742, 745->746, 757->758, 773->771, 1399->1400, 1471->1472, 1489->1490, 1592->1593, 1644->1645, 1762->1763, 1766->1767, 1768->1769, 1956->1957, 2064->2058, 2129->2130, 2212->2213, 2220->2221, 2229->2230, 2234->2235 |
| `src/pystachy_compiler/exceptions.py` | 1121 | 1120->1121 |
| `src/pystachy_compiler/expressions.py` | 3256, 3332-3333 | 928->929, 1006->1007, 1902->1904, 3255->3256, 3331->3332 |
| `src/pystachy_compiler/functions.py` | 145 | 144->145 |
| `src/pystachy_compiler/generators.py` | 705 | 704->705 |
| `src/pystachy_compiler/ircheck.py` | 179 | 178->179, 197->198 |
| `src/pystachy_compiler/loader.py` | 531, 931, 940, 945-946, 956, 1102 | 530->531, 664->661, 927->946, 930->931, 932->945, 939->940, 955->956, 1097->1102, 1332->1335 |
| `src/pystachy_compiler/lower_module.py` | 30-36 | 31->32, 31->36, 32->33, 32->35 |
| `src/pystachy_compiler/optimizations.py` | 907, 950, 954 | 304->305, 717->723, 739->734, 768->761, 906->907, 909->908, 949->950, 953->954, 960->959, 961->959 |
| `src/pystachy_compiler/reflection.py` | 292, 305-308 | 291->292, 293->305, 306->307, 306->308 |
| `src/pystachy_compiler/union_proof.py` | 45, 48, 54, 104, 147, 183, 207, 554, 556, 558, 622, 629, 739 | 44->45, 47->48, 53->54, 64->68, 103->104, 143->145, 146->147, 182->183, 206->207, 214->223, 239->237, 366->372, 403->405, 409->419, 415->409, 553->554, 555->556, 557->558, 621->622, 628->629, 735->754, 738->739, 807->830 |
| `src/pystachy_compiler/union_state.py` | 90, 147 | 89->90, 146->147 |
| `src/pystachy_compiler/variables.py` | 540, 596, 630, 1602-1603, 1812, 1833, 1887-1888 | 539->540, 629->630, 1601->1602, 1811->1812, 1830->1833, 1887->1888, 1887->1889 |

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1442 | 73 | 94.9% | 1234 | 84 | 93.2% | 94.1% | 94.1% |
| `src/pystachy_compiler/builtins.py` | 2218 | 100 | 95.5% | 1316 | 96 | 92.7% | 94.5% | 94.2% |
| `src/pystachy_compiler/calls.py` | 1211 | 52 | 95.7% | 750 | 52 | 93.1% | 94.7% | 92.2% |
| `src/pystachy_compiler/containers.py` | 789 | 31 | 96.1% | 428 | 33 | 92.3% | 94.7% | 94.7% |
| `src/pystachy_compiler/conversions.py` | 258 | 8 | 96.9% | 156 | 6 | 96.2% | 96.6% | 96.6% |
| `src/pystachy_compiler/declarations.py` | 2293 | 143 | 93.8% | 1546 | 133 | 91.4% | 92.8% | 92.1% |
| `src/pystachy_compiler/diagnostics.py` | 48 | 0 | 100.0% | 14 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/driver.py` | 575 | 77 | 86.6% | 236 | 48 | 79.7% | 84.6% | 68.6% |
| `src/pystachy_compiler/dynamic.py` | 1590 | 100 | 93.7% | 794 | 93 | 88.3% | 91.9% | 91.9% |
| `src/pystachy_compiler/emission.py` | 486 | 13 | 97.3% | 144 | 10 | 93.1% | 96.3% | 96.0% |
| `src/pystachy_compiler/exceptions.py` | 1164 | 33 | 97.2% | 550 | 29 | 94.7% | 96.4% | 96.4% |
| `src/pystachy_compiler/expressions.py` | 3505 | 97 | 97.2% | 2078 | 100 | 95.2% | 96.5% | 96.5% |
| `src/pystachy_compiler/flow.py` | 766 | 6 | 99.2% | 534 | 10 | 98.1% | 98.8% | 98.1% |
| `src/pystachy_compiler/functions.py` | 326 | 10 | 96.9% | 180 | 8 | 95.6% | 96.4% | 78.5% |
| `src/pystachy_compiler/gen.py` | 2267 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 926 | 40 | 95.7% | 372 | 45 | 87.9% | 93.5% | 93.5% |
| `src/pystachy_compiler/ir.py` | 343 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 394 | 26 | 93.4% | 324 | 26 | 92.0% | 92.8% | 77.4% |
| `src/pystachy_compiler/lexer.py` | 637 | 27 | 95.8% | 356 | 26 | 92.7% | 94.7% | 94.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2530 | 75 | 97.0% | 1560 | 82 | 94.7% | 96.2% | 95.9% |
| `src/pystachy_compiler/local_versions.py` | 38 | 0 | 100.0% | 26 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 359 | 11 | 96.9% | 186 | 7 | 96.2% | 96.7% | 53.0% |
| `src/pystachy_compiler/lowering.py` | 394 | 3 | 99.2% | 238 | 4 | 98.3% | 98.9% | 98.7% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 30 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 27 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 811 | 13 | 98.4% | 514 | 25 | 95.1% | 97.1% | 96.8% |
| `src/pystachy_compiler/parser.py` | 1999 | 103 | 94.8% | 1110 | 101 | 90.9% | 93.4% | 93.4% |
| `src/pystachy_compiler/program.py` | 934 | 35 | 96.3% | 684 | 33 | 95.2% | 95.8% | 94.8% |
| `src/pystachy_compiler/reflection.py` | 1925 | 145 | 92.5% | 1024 | 138 | 86.5% | 90.4% | 90.3% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/specs.py` | 241 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1629 | 63 | 96.1% | 898 | 67 | 92.5% | 94.9% | 94.7% |
| `src/pystachy_compiler/structs.py` | 224 | 27 | 87.9% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 146 | 4 | 97.3% | 98 | 5 | 94.9% | 96.3% | 96.3% |
| `src/pystachy_compiler/templates.py` | 720 | 39 | 94.6% | 436 | 47 | 89.2% | 92.6% | 92.6% |
| `src/pystachy_compiler/union_arithmetic.py` | 115 | 3 | 97.4% | 50 | 3 | 94.0% | 96.4% | 96.4% |
| `src/pystachy_compiler/union_proof.py` | 762 | 13 | 98.3% | 544 | 23 | 95.8% | 97.2% | 92.2% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 416 | 29 | 93.0% | 220 | 27 | 87.7% | 91.2% | 91.2% |
| `src/pystachy_compiler/utils.py` | 573 | 24 | 95.8% | 282 | 22 | 92.2% | 94.6% | 93.8% |
| `src/pystachy_compiler/variables.py` | 1709 | 99 | 94.2% | 1064 | 104 | 90.2% | 92.7% | 92.6% |
