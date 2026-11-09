## Hosted compiler coverage

Commit `ce8c887feaee5c8c038d9da5f09c68f8bd9a83f7` with uncommitted changes: statements **55.4%** (26709 of 48235) and branches **47.9%** (12514 of 26142); 52.7% together, coverage.py's total. 2 suites, 16 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT, 3 cases selected | 6 passed, 0 failed | 7 | 21 s | 35.9% | 26.7% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 448 tests, OK | 9 | 40 s | 52.4% | 45.2% |
| **all** | | | **16** | | **55.4%** | **47.9%** |

The other suites run 9381 statements and 5546 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1591 | 576 | 63.8% | 1352 | 567 | 58.1% | 61.2% | 43.1% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 302 | 9.0% | 210 | 207 | 1.4% | 6.1% | 6.1% |
| `src/pystachy_compiler/bigints.py` | 969 | 676 | 30.2% | 400 | 349 | 12.8% | 25.1% | 12.5% |
| `src/pystachy_compiler/builtins.py` | 2583 | 1606 | 37.8% | 1572 | 984 | 37.4% | 37.7% | 19.7% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 224 | 59 | 73.7% | 110 | 35 | 68.2% | 71.9% | 13.5% |
| `src/pystachy_compiler/callbacks.py` | 180 | 2 | 98.9% | 90 | 3 | 96.7% | 98.1% | 5.2% |
| `src/pystachy_compiler/calls.py` | 1388 | 611 | 56.0% | 848 | 437 | 48.5% | 53.1% | 25.0% |
| `src/pystachy_compiler/containers.py` | 976 | 700 | 28.3% | 524 | 397 | 24.2% | 26.9% | 16.5% |
| `src/pystachy_compiler/conversions.py` | 305 | 94 | 69.2% | 200 | 76 | 62.0% | 66.3% | 38.8% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 6 | 97.3% | 122 | 7 | 94.3% | 96.2% | 6.1% |
| `src/pystachy_compiler/declarations.py` | 2381 | 1222 | 48.7% | 1610 | 896 | 44.3% | 46.9% | 26.3% |
| `src/pystachy_compiler/diagnostics.py` | 84 | 14 | 83.3% | 20 | 7 | 65.0% | 79.8% | 74.0% |
| `src/pystachy_compiler/driver.py` | 811 | 247 | 69.5% | 338 | 152 | 55.0% | 65.3% | 59.5% |
| `src/pystachy_compiler/dynamic.py` | 3934 | 2475 | 37.1% | 2064 | 1454 | 29.6% | 34.5% | 29.2% |
| `src/pystachy_compiler/emission.py` | 550 | 61 | 88.9% | 180 | 42 | 76.7% | 85.9% | 73.6% |
| `src/pystachy_compiler/exceptions.py` | 1263 | 698 | 44.7% | 622 | 377 | 39.4% | 43.0% | 24.2% |
| `src/pystachy_compiler/expressions.py` | 4266 | 2255 | 47.1% | 2484 | 1384 | 44.3% | 46.1% | 24.3% |
| `src/pystachy_compiler/flow.py` | 785 | 132 | 83.2% | 550 | 128 | 76.7% | 80.5% | 57.8% |
| `src/pystachy_compiler/functions.py` | 414 | 126 | 69.6% | 230 | 91 | 60.4% | 66.3% | 57.5% |
| `src/pystachy_compiler/gen.py` | 2671 | 447 | 83.3% | 2 | 0 | 100.0% | 83.3% | 74.1% |
| `src/pystachy_compiler/generators.py` | 1010 | 454 | 55.0% | 402 | 222 | 44.8% | 52.1% | 26.3% |
| `src/pystachy_compiler/ir.py` | 394 | 12 | 97.0% | 16 | 0 | 100.0% | 97.1% | 90.5% |
| `src/pystachy_compiler/ircheck.py` | 432 | 27 | 93.8% | 356 | 27 | 92.4% | 93.1% | 66.5% |
| `src/pystachy_compiler/lexer.py` | 636 | 226 | 64.5% | 356 | 152 | 57.3% | 61.9% | 54.7% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2987 | 1565 | 47.6% | 1866 | 1127 | 39.6% | 44.5% | 33.4% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 91.8% |
| `src/pystachy_compiler/lower_module.py` | 443 | 217 | 51.0% | 238 | 122 | 48.7% | 50.2% | 44.2% |
| `src/pystachy_compiler/lowering.py` | 516 | 30 | 94.2% | 302 | 18 | 94.0% | 94.1% | 74.0% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 31 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 28 | 2 | 92.9% | 12 | 2 | 83.3% | 90.0% | 90.0% |
| `src/pystachy_compiler/optimizations.py` | 1247 | 34 | 97.3% | 788 | 46 | 94.2% | 96.1% | 50.5% |
| `src/pystachy_compiler/parser.py` | 2091 | 889 | 57.5% | 1168 | 626 | 46.4% | 53.5% | 41.4% |
| `src/pystachy_compiler/program.py` | 1039 | 410 | 60.5% | 758 | 322 | 57.5% | 59.3% | 43.2% |
| `src/pystachy_compiler/program_cache.py` | 572 | 69 | 87.9% | 236 | 29 | 87.7% | 87.9% | 10.1% |
| `src/pystachy_compiler/reflection.py` | 2521 | 2203 | 12.6% | 1330 | 1224 | 8.0% | 11.0% | 9.0% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 110 | 79.4% | 294 | 92 | 68.7% | 75.6% | 57.1% |
| `src/pystachy_compiler/source_lines.py` | 128 | 1 | 99.2% | 60 | 4 | 93.3% | 97.3% | 18.1% |
| `src/pystachy_compiler/specs.py` | 261 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 99.4% |
| `src/pystachy_compiler/statements.py` | 1721 | 738 | 57.1% | 946 | 432 | 54.3% | 56.1% | 35.9% |
| `src/pystachy_compiler/structs.py` | 225 | 206 | 8.4% | 128 | 128 | 0.0% | 5.4% | 5.4% |
| `src/pystachy_compiler/syntax.py` | 154 | 37 | 76.0% | 100 | 36 | 64.0% | 71.3% | 57.9% |
| `src/pystachy_compiler/templates.py` | 799 | 392 | 50.9% | 478 | 302 | 36.8% | 45.7% | 22.3% |
| `src/pystachy_compiler/union_arithmetic.py` | 133 | 73 | 45.1% | 52 | 25 | 51.9% | 47.0% | 4.9% |
| `src/pystachy_compiler/union_proof.py` | 795 | 31 | 96.1% | 572 | 40 | 93.0% | 94.8% | 1.9% |
| `src/pystachy_compiler/union_state.py` | 210 | 3 | 98.6% | 112 | 3 | 97.3% | 98.1% | 6.2% |
| `src/pystachy_compiler/unions.py` | 458 | 134 | 70.7% | 246 | 105 | 57.3% | 66.1% | 11.1% |
| `src/pystachy_compiler/utils.py` | 755 | 217 | 71.3% | 388 | 162 | 58.2% | 66.8% | 47.8% |
| `src/pystachy_compiler/variables.py` | 1823 | 1114 | 38.9% | 1140 | 771 | 32.4% | 36.4% | 17.2% |
