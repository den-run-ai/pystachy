## Hosted compiler coverage

Commit `5f81cc2563d231501952104e991d858e670325ac`: statements **95.7%** (48054 of 50218) and branches **92.3%** (25083 of 27184); 94.5% together, coverage.py's total. 5 suites, 7467 processes measured.
The statements and branches of `src/pystachy_compiler/`, run by CPython; not `runtime.c`, `runtime.py`, `lib/` or the compiled programs, which run as native code ([native runtime coverage](https://github.com/den-run-ai/pystachy/blob/badges/runtime-coverage.md)).

| Suite | Runs | Checks | Processes | Time | Statements | Branches |
|---|---|---|---:|---:|---:|---:|
| corpus | `tests/run.sh`, JIT and AOT (10 shards) | 7125 passed, 0 failed | 7135 | 4323 s | 92.5% | 88.7% |
| ffi | `tests/ffi/run.sh`, JIT and AOT | 194 passed, 0 failed; skipped: py_coerce (the CPython-hosted compiler's own locale coercion reaches the program) | 175 | 173 s | 49.5% | 42.1% |
| cache | `tests/cache.sh` | 84 passed, 0 failed | 45 | 279 s | 27.5% | 18.3% |
| unit | `tools/test_typed*.py`, `tools/test_function_summaries.py`, the native program cache's, `--emit-ir`'s, the C runtime cache's, `ctypes_schema.py`'s and `source_lines.py`'s | 526 tests, OK | 9 | 70 s | 52.8% | 45.8% |
| ir | `tools/check_ir.sh`: `pystachy.py`, `runtime.py`, `bench/`, the `tests/ir/` contracts | the IR check and llvm-as accept the IR of 103 programs | 103 | 132 s | 60.6% | 54.1% |
| **all** | | | **7467** | | **95.7%** | **92.3%** |

The other suites run 1612 statements and 979 branches that the corpus does not.

| Module | Statements | Missed | Statements % | Branches | Missed | Branches % | Total | Corpus alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `src/pystachy_compiler/analysis.py` | 1591 | 73 | 95.4% | 1352 | 86 | 93.6% | 94.6% | 94.5% |
| `src/pystachy_compiler/argparse_schema.py` | 332 | 25 | 92.5% | 210 | 27 | 87.1% | 90.4% | 90.4% |
| `src/pystachy_compiler/bigints.py` | 969 | 38 | 96.1% | 400 | 42 | 89.5% | 94.2% | 94.2% |
| `src/pystachy_compiler/builtins.py` | 2745 | 128 | 95.3% | 1646 | 125 | 92.4% | 94.2% | 93.2% |
| `src/pystachy_compiler/cache_toolchain.py` | 245 | 23 | 90.6% | 132 | 18 | 86.4% | 89.1% | 6.1% |
| `src/pystachy_compiler/cached_run.py` | 226 | 59 | 73.9% | 110 | 35 | 68.2% | 72.0% | 13.7% |
| `src/pystachy_compiler/callbacks.py` | 180 | 2 | 98.9% | 90 | 3 | 96.7% | 98.1% | 96.7% |
| `src/pystachy_compiler/calls.py` | 1388 | 49 | 96.5% | 848 | 48 | 94.3% | 95.7% | 93.7% |
| `src/pystachy_compiler/containers.py` | 976 | 37 | 96.2% | 524 | 39 | 92.6% | 94.9% | 94.9% |
| `src/pystachy_compiler/conversions.py` | 313 | 10 | 96.8% | 202 | 8 | 96.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/ctypes_schema.py` | 221 | 2 | 99.1% | 122 | 2 | 98.4% | 98.8% | 37.3% |
| `src/pystachy_compiler/declarations.py` | 2408 | 140 | 94.2% | 1624 | 133 | 91.8% | 93.2% | 92.6% |
| `src/pystachy_compiler/diagnostics.py` | 84 | 8 | 90.5% | 20 | 1 | 95.0% | 91.3% | 91.3% |
| `src/pystachy_compiler/driver.py` | 981 | 160 | 83.7% | 410 | 110 | 73.2% | 80.6% | 64.0% |
| `src/pystachy_compiler/dynamic.py` | 3952 | 227 | 94.3% | 2064 | 250 | 87.9% | 92.1% | 92.1% |
| `src/pystachy_compiler/dynamic_proof.py` | 409 | 4 | 99.0% | 248 | 7 | 97.2% | 98.3% | 93.2% |
| `src/pystachy_compiler/emission.py` | 552 | 16 | 97.1% | 182 | 13 | 92.9% | 96.0% | 94.1% |
| `src/pystachy_compiler/exceptions.py` | 1393 | 45 | 96.8% | 670 | 41 | 93.9% | 95.8% | 95.8% |
| `src/pystachy_compiler/expressions.py` | 4437 | 133 | 97.0% | 2582 | 124 | 95.2% | 96.3% | 96.3% |
| `src/pystachy_compiler/flow.py` | 828 | 4 | 99.5% | 576 | 9 | 98.4% | 99.1% | 98.4% |
| `src/pystachy_compiler/functions.py` | 414 | 23 | 94.4% | 230 | 17 | 92.6% | 93.8% | 79.7% |
| `src/pystachy_compiler/gen.py` | 2698 | 1 | 99.9% | 2 | 0 | 100.0% | 99.9% | 99.7% |
| `src/pystachy_compiler/generators.py` | 1010 | 37 | 96.3% | 402 | 43 | 89.3% | 94.3% | 94.3% |
| `src/pystachy_compiler/ir.py` | 421 | 3 | 99.3% | 32 | 3 | 90.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/ircheck.py` | 471 | 28 | 94.1% | 392 | 28 | 92.9% | 93.5% | 78.3% |
| `src/pystachy_compiler/lexer.py` | 636 | 26 | 95.9% | 356 | 25 | 93.0% | 94.9% | 94.9% |
| `src/pystachy_compiler/llvm_abi.py` | 12 | 0 | 100.0% | 4 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/loader.py` | 2987 | 110 | 96.3% | 1866 | 119 | 93.6% | 95.3% | 95.1% |
| `src/pystachy_compiler/local_versions.py` | 43 | 0 | 100.0% | 30 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/lower_module.py` | 444 | 11 | 97.5% | 238 | 7 | 97.1% | 97.4% | 58.4% |
| `src/pystachy_compiler/lowering.py` | 531 | 3 | 99.4% | 308 | 5 | 98.4% | 99.0% | 98.9% |
| `src/pystachy_compiler/memory_ir.py` | 17 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/module.py` | 31 | 0 | 100.0% | 0 | 0 | - | 100.0% | 100.0% |
| `src/pystachy_compiler/names.py` | 28 | 0 | 100.0% | 12 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/optimizations.py` | 1662 | 36 | 97.8% | 1004 | 43 | 95.7% | 97.0% | 96.5% |
| `src/pystachy_compiler/parser.py` | 2098 | 104 | 95.0% | 1170 | 102 | 91.3% | 93.7% | 93.7% |
| `src/pystachy_compiler/patterns.py` | 235 | 15 | 93.6% | 132 | 13 | 90.2% | 92.4% | 92.4% |
| `src/pystachy_compiler/program.py` | 1044 | 38 | 96.4% | 762 | 39 | 94.9% | 95.7% | 94.9% |
| `src/pystachy_compiler/program_cache.py` | 584 | 69 | 88.2% | 240 | 29 | 87.9% | 88.1% | 11.8% |
| `src/pystachy_compiler/reflection.py` | 2525 | 171 | 93.2% | 1334 | 167 | 87.5% | 91.2% | 91.1% |
| `src/pystachy_compiler/scalar_ir.py` | 47 | 0 | 100.0% | 22 | 0 | 100.0% | 100.0% | 73.9% |
| `src/pystachy_compiler/scope.py` | 534 | 4 | 99.3% | 294 | 7 | 97.6% | 98.7% | 98.7% |
| `src/pystachy_compiler/source_lines.py` | 128 | 1 | 99.2% | 60 | 4 | 93.3% | 97.3% | 18.1% |
| `src/pystachy_compiler/specs.py` | 266 | 0 | 100.0% | 86 | 0 | 100.0% | 100.0% | 100.0% |
| `src/pystachy_compiler/statements.py` | 1744 | 62 | 96.4% | 962 | 68 | 92.9% | 95.2% | 95.1% |
| `src/pystachy_compiler/structs.py` | 225 | 27 | 88.0% | 128 | 23 | 82.0% | 85.8% | 85.8% |
| `src/pystachy_compiler/syntax.py` | 154 | 4 | 97.4% | 100 | 5 | 95.0% | 96.5% | 96.5% |
| `src/pystachy_compiler/templates.py` | 799 | 37 | 95.4% | 478 | 45 | 90.6% | 93.6% | 93.6% |
| `src/pystachy_compiler/union_arithmetic.py` | 139 | 3 | 97.8% | 56 | 3 | 94.6% | 96.9% | 96.9% |
| `src/pystachy_compiler/union_proof.py` | 807 | 13 | 98.4% | 584 | 23 | 96.1% | 97.4% | 92.1% |
| `src/pystachy_compiler/union_state.py` | 210 | 2 | 99.0% | 112 | 2 | 98.2% | 98.8% | 96.6% |
| `src/pystachy_compiler/unions.py` | 458 | 22 | 95.2% | 246 | 22 | 91.1% | 93.8% | 93.8% |
| `src/pystachy_compiler/utils.py` | 759 | 29 | 96.2% | 388 | 28 | 92.8% | 95.0% | 91.5% |
| `src/pystachy_compiler/variables.py` | 1827 | 102 | 94.4% | 1142 | 110 | 90.4% | 92.9% | 92.8% |
