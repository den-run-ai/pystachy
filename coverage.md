## Hosted compiler coverage

Commit `817c9cd9e8a638232a65adb916af39735e503282`: statements **95.7%** (55157 of 57646) and branches **92.1%** (28711 of 31158); 94.4% together, coverage.py's total. 5 suites, 9146 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 8794 passed, 0 failed | 8804 | 5074 s | 92.8% | 88.8% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 194 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 175 | 279 s | 46.8% | 39.2% |
| cache | `tests/cache.sh` | 99 passed, 0 failed | 53 | 312 s | 32.3% | 23.3% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 618 tests, OK | 9 | 72 s | 50.3% | 43.3% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 105 programs | 105 | 384 s | 57.4% | 50.6% |
| **all** | | | **9146** | | **95.7%** | **92.1%** |

The other suites run 1668 statements and 1031 branches that the corpus does not.

### Changed since d58034c1ca588c90363b8deb3b3c633b1cc90c47 (merge base `d58034c1ca58`)

Changed statements: 5780 of 6100 run (94.8%); their branches: 2947 of 3294 taken (89.5%).

| File | Statements not run | Branches not taken |
|---|---|---|
| `src/pystachy_compiler/analysis.py` | 423, 437, 467, 469, 472, 491, 505 | 422->423, 436->437, 466->467, 468->469, 471->472, 490->491, 504->505 |
| `src/pystachy_compiler/builtins.py` | 317, 411, 415, 422, 754, 824, 2213, 2226, 2232, 2247, 2250, 2502, 2504, 2819 | 316->317, 410->411, 414->415, 421->422, 753->754, 821->824, 2211->2213, 2221->2230, 2222->2225, 2225->2226, 2231->2232, 2235->2240, 2246->2247, 2249->2250, 2501->2502, 2503->2504, 2818->2819 |
| `src/pystachy_compiler/calls.py` | 1495 | 546->545, 1494->1495 |
| `src/pystachy_compiler/class_values.py` | 61, 64, 70, 74, 129, 160, 257, 273, 276, 286, 320, 343, 375, 406, 437, 464, 506, 524-525, 527, 542, 576, 625, 689, 704, 738 | 60->61, 63->64, 69->70, 73->74, 128->129, 159->160, 200->198, 256->257, 271->273, 275->276, 284->286, 319->320, 342->343, 374->375, 405->406, 436->437, 463->464, 502->506, 504->502, 523->524, 526->527, 541->542, 575->576, 624->625, 688->689, 703->704, 737->738, 755->762 |
| `src/pystachy_compiler/containers.py` | 447, 488, 1445 | 446->447, 486->488, 1444->1445 |
| `src/pystachy_compiler/dataflow.py` | - | 62->72, 68->62 |
| `src/pystachy_compiler/declarations.py` | 414, 1776-1777, 2109-2110, 2589, 2610, 2623, 2789-2792, 2821, 2844, 3008, 3029, 3041-3042, 3079, 3143, 3195-3201, 3203-3206, 3211-3219, 3230, 3493 | 413->414, 1773->1776, 1776->1771, 1776->1777, 2108->2109, 2588->2589, 2609->2610, 2622->2623, 2631->exit, 2760->2762, 2765->2767, 2787->2789, 2791->2792, 2791->2793, 2820->2821, 2837->2842, 2843->2844, 2869->2866, 2873->2875, 3007->3008, 3011->3015, 3028->3029, 3040->3041, 3078->3079, 3142->3143, 3197->3198, 3197->3204, 3198->3199, 3198->3203, 3199->3200, 3199->3201, 3204->3205, 3204->3206, 3211->3212, 3211->3213, 3213->3214, 3213->3219, 3214->3213, 3214->3215, 3216->3213, 3216->3217, 3217->3216, 3217->3218, 3226->3230, 3490->3493 |
| `src/pystachy_compiler/driver.py` | 561, 563, 565-567, 808, 1503 | 560->561, 562->563, 564->565, 565->566, 565->567, 807->808, 1499->1503 |
| `src/pystachy_compiler/dynamic.py` | 2458, 4311, 4313, 4329, 4331, 4333, 4359-4360, 4375-4376, 4378, 4380, 4403, 4418-4419, 4421-4428, 4430-4431, 4477-4478, 4480, 4488 | 2457->2458, 4310->4311, 4312->4313, 4328->4329, 4330->4331, 4332->4333, 4358->4359, 4373->4375, 4375->4376, 4375->4378, 4379->4380, 4402->4403, 4409->4408, 4417->4418, 4425->4426, 4425->4431, 4426->4427, 4426->4430, 4427->4428, 4427->4431, 4475->4477, 4477->4478, 4477->4480, 4487->4488 |
| `src/pystachy_compiler/dynamic_proof.py` | - | 410->exit |
| `src/pystachy_compiler/emission.py` | 41 | 38->41, 58->62 |
| `src/pystachy_compiler/expressions.py` | 163, 175, 200, 202, 1178, 1776, 2310, 2312, 3455, 3843, 4387, 4681, 5154, 5170, 5618, 5773, 5777, 6184, 6188 | 162->163, 164->161, 172->175, 199->200, 201->202, 1177->1178, 1775->1776, 2306->2314, 2309->2310, 2311->2312, 2412->2421, 2431->2434, 3454->3455, 3842->3843, 4386->4387, 4661->4666, 4680->4681, 4694->4693, 5153->5154, 5168->5170, 5616->5618, 5772->5773, 5776->5777, 6182->6184, 6187->6188 |
| `src/pystachy_compiler/gen.py` | 3381 | - |
| `src/pystachy_compiler/ir.py` | 95, 132 | 94->95, 131->132 |
| `src/pystachy_compiler/lexer.py` | 37, 343-344 | 36->37, 342->343 |
| `src/pystachy_compiler/loader.py` | 123, 193, 196, 199, 202, 204-206, 357, 403, 602, 648, 653, 655, 665, 669, 694, 699-700, 711, 714-715, 737, 830, 950, 958, 976, 1123-1124, 1167-1170, 1192, 1213, 1219, 1224, 1461, 2843, 2850, 2907, 2917, 2924, 2929, 2938, 3127, 3141, 3143, 3151, 3154-3156, 3158, 3203, 3205, 3211, 4913, 4981, 4985, 4997, 5000 | 122->123, 192->193, 195->196, 198->199, 201->202, 203->204, 205->206, 205->207, 225->227, 356->357, 402->403, 601->602, 647->648, 652->653, 654->655, 664->665, 668->669, 693->694, 696->699, 699->691, 699->700, 705->726, 710->711, 712->714, 714->705, 714->715, 722->724, 724->721, 736->737, 829->830, 922->923, 949->950, 957->958, 975->976, 1022->1013, 1122->1123, 1123->1113, 1123->1124, 1166->1167, 1167->1168, 1167->1169, 1169->1166, 1169->1170, 1191->1192, 1212->1213, 1218->1219, 1223->1224, 1460->1461, 2035->2037, 2842->2843, 2849->2850, 2906->2907, 2916->2917, 2923->2924, 2928->2929, 2930->2938, 3126->3127, 3140->3141, 3142->3143, 3150->3151, 3153->3154, 3154->3155, 3154->3156, 3157->3158, 3202->3203, 3204->3205, 3210->3211, 4910->4913, 4959->4961, 4980->4981, 4984->4985, 4996->4997, 4999->5000, 5113->5111 |
| `src/pystachy_compiler/lower_module.py` | 88-93 | 89->90, 89->93, 90->91, 90->92 |
| `src/pystachy_compiler/optimizations.py` | 666, 670, 885, 1020-1021 | 665->666, 669->670, 865->864, 884->885, 1019->1020, 1119->1125 |
| `src/pystachy_compiler/patterns.py` | 321-326, 359, 361 | 318->321, 321->322, 321->323, 323->324, 323->325, 325->326, 325->327, 356->357, 358->359, 360->361 |
| `src/pystachy_compiler/program.py` | 103, 116, 146, 154, 165, 168, 170, 181, 310, 317-320, 340, 356, 360, 482-483, 622-623, 626, 699, 722, 751, 760, 1647, 1654, 1665, 1685, 1704, 1707, 1711, 1719, 1725, 1729, 1732, 1736 | 87->90, 88->87, 102->103, 115->116, 145->146, 153->154, 164->165, 167->168, 169->170, 180->181, 212->213, 309->310, 314->317, 318->319, 318->320, 339->340, 355->356, 359->360, 481->482, 516->515, 621->622, 622->621, 622->623, 625->626, 644->643, 698->699, 718->722, 750->751, 757->760, 1646->1647, 1653->1654, 1664->1665, 1684->1685, 1702->1704, 1706->1707, 1710->1711, 1718->1719, 1724->1725, 1728->1729, 1731->1732, 1735->1736, 1937->1936 |
| `src/pystachy_compiler/reflection.py` | 180, 186, 188, 569, 3143 | 179->180, 185->186, 187->188, 568->569, 3142->3143 |
| `src/pystachy_compiler/statements.py` | 1582, 1676, 1693, 1696-1704 | 1581->1582, 1674->1666, 1675->1676, 1692->1693, 1695->1696, 1697->1698, 1697->1699, 1968->1970 |
| `src/pystachy_compiler/templates.py` | 460 | 459->460 |
| `src/pystachy_compiler/union_arithmetic.py` | 24-29, 76, 140-141, 284-285 | 22->24, 24->25, 24->26, 26->27, 26->29, 72->81, 73->72, 74->76, 90->93, 136->140, 283->284 |
| `src/pystachy_compiler/union_proof.py` | - | 916->exit |
| `src/pystachy_compiler/unions.py` | 596, 598, 628, 680, 691, 715, 721, 747, 913 | 75->77, 99->101, 595->596, 597->598, 627->628, 679->680, 688->691, 714->715, 720->721, 746->747, 911->913 |
| `src/pystachy_compiler/utils.py` | 253, 255 | 252->253, 254->255, 264->265 |
| `src/pystachy_compiler/variables.py` | 681, 894, 1229, 1586-1589, 1721 | 677->681, 1226->1229, 1585->1586, 1717->1721 |

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
| `src/pystachy_compiler/dynamic.py` | 4272 | 251 | 94.1% | 2226 | 269 | 87.9% | 92.0% | 92.0% |
| `src/pystachy_compiler/dynamic_proof.py` | 336 | 4 | 98.8% | 190 | 4 | 97.9% | 98.5% | 92.6% |
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
| `src/pystachy_compiler/statements.py` | 1921 | 75 | 96.1% | 1054 | 77 | 92.7% | 94.9% | 94.8% |
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
