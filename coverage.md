## Hosted compiler coverage

Commit `7f9aab19883c2f850464f62cb68439a9139506a4`: statements **93.9%** (45281 of 48214) and branches **90.5%** (23656 of 26126); 92.7% together, coverage.py's total. 5 suites, 7164 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (8 shards) | 6845 passed, 0 failed | 6853 | 4396 s | 92.4% | 88.6% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 194 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 175 | 184 s | 49.1% | 41.5% |
| cache | `tests/cache.sh` | 68 passed, 0 failed | 34 | 227 s | 27.1% | 17.8% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py` | 248 tests, OK | 2 | 14 s | 49.7% | 42.3% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 100 programs | 100 | 155 s | 60.2% | 53.4% |
| **all** | | | **7164** | | **93.9%** | **90.5%** |

The other suites run 747 statements and 508 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1591 | 73 | 95.4% | 1352 | 86 | 93.6% | 94.6% | 94.5% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 969 | 38 | 96.1% | 400 | 42 | 89.5% | 94.2% | 94.2% |
| `src/pystachy_compiler/builtins.py` | 2579 | 121 | 95.3% | 1568 | 115 | 92.7% | 94.3% | 93.4% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 222 | 9.4% | 132 | 132 | 0.0% | 6.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 235 | 196 | 16.6% | 116 | 110 | 5.2% | 12.8% | 12.8% |
| `src/pystachy_compiler/callbacks.py` | 180 | 2 | 98.9% | 90 | 3 | 96.7% | 98.1% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1388 | 49 | 96.5% | 848 | 48 | 94.3% | 95.7% | 93.5% |
| `src/pystachy_compiler/containers.py` | 976 | 37 | 96.2% | 524 | 39 | 92.6% | 94.9% | 94.9% |
| `src/pystachy_compiler/conversions.py` | 305 | 10 | 96.7% | 200 | 8 | 96.0% | 96.4% | 96.4% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 14 | 93.7% | 122 | 14 | 88.5% | 91.8% | 37.3% |
| `src/pystachy_compiler/declarations.py` | 2381 | 140 | 94.1% | 1610 | 133 | 91.7% | 93.2% | 92.5% |
| `src/pystachy_compiler/diagnostics.py` | 84 | 8 | 90.5% | 20 | 1 | 95.0% | 91.3% | 91.3% |
| `src/pystachy_compiler/driver.py` | 785 | 169 | 78.5% | 320 | 99 | 69.1% | 75.7% | 63.4% |
| `src/pystachy_compiler/dynamic.py` | 3934 | 233 | 94.1% | 2064 | 253 | 87.7% | 91.9% | 91.9% |
| `src/pystachy_compiler/emission.py` | 550 | 16 | 97.1% | 180 | 13 | 92.8% | 96.0% | 94.1% |
| `src/pystachy_compiler/exceptions.py` | 1263 | 42 | 96.7% | 622 | 39 | 93.7% | 95.7% | 95.7% |
| `src/pystachy_compiler/expressions.py` | 4266 | 130 | 97.0% | 2484 | 120 | 95.2% | 96.3% | 96.3% |
| `src/pystachy_compiler/flow.py` | 785 | 4 | 99.5% | 550 | 9 | 98.4% | 99.0% | 98.4% |
| `src/pystachy_compiler/functions.py` | 414 | 23 | 94.4% | 230 | 17 | 92.6% | 93.8% | 79.7% |
| `src/pystachy_compiler/gen.py` | 2671 | 3 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1010 | 36 | 96.4% | 402 | 42 | 89.6% | 94.5% | 94.5% |
| `src/pystachy_compiler/ir.py` | 394 | 0 | 100.0% | 16 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/ircheck.py` | 432 | 27 | 93.8% | 356 | 27 | 92.4% | 93.1% | 78.0% |
| `src/pystachy_compiler/lexer.py` | 636 | 26 | 95.9% | 356 | 25 | 93.0% | 94.9% | 94.9% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2987 | 111 | 96.3% | 1866 | 120 | 93.6% | 95.2% | 95.1% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 443 | 11 | 97.5% | 238 | 7 | 97.1% | 97.4% | 58.3% |
| `src/pystachy_compiler/lowering.py` | 516 | 3 | 99.4% | 302 | 5 | 98.3% | 99.0% | 98.9% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 31 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 28 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1247 | 22 | 98.2% | 788 | 31 | 96.1% | 97.4% | 96.8% |
| `src/pystachy_compiler/parser.py` | 2091 | 104 | 95.0% | 1168 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/program.py` | 1039 | 37 | 96.4% | 758 | 37 | 95.1% | 95.9% | 95.0% |
| `src/pystachy_compiler/program_cache.py` | 570 | 491 | 13.9% | 236 | 234 | 0.8% | 10.0% | 10.0% |
| `src/pystachy_compiler/reflection.py` | 2521 | 193 | 92.3% | 1330 | 181 | 86.4% | 90.3% | 90.2% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 128 | 8 | 93.8% | 60 | 12 | 80.0% | 89.4% | 18.1% |
| `src/pystachy_compiler/specs.py` | 261 | 0 | 100.0% | 82 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1721 | 61 | 96.5% | 946 | 67 | 92.9% | 95.2% | 95.1% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 154 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 799 | 38 | 95.2% | 478 | 46 | 90.4% | 93.4% | 93.4% |
| `src/pystachy_compiler/union_arithmetic.py` | 133 | 3 | 97.7% | 52 | 3 | 94.2% | 96.8% | 96.8% |
| `src/pystachy_compiler/union_proof.py` | 795 | 13 | 98.4% | 572 | 23 | 96.0% | 97.4% | 92.7% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 458 | 23 | 95.0% | 246 | 23 | 90.7% | 93.5% | 93.5% |
| `src/pystachy_compiler/utils.py` | 755 | 32 | 95.8% | 388 | 30 | 92.3% | 94.6% | 91.3% |
| `src/pystachy_compiler/variables.py` | 1823 | 102 | 94.4% | 1140 | 110 | 90.4% | 92.8% | 92.8% |
