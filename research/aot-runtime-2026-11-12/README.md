# Precompiled runtime for AOT builds (#706), 12 November 2026

Raw evaluation for a research branch; not for merging. Prepared with Claude Code assistance at
the repository owner's request. The change is commit `c739499c` on branch
`claude/peaceful-faraday-2yr9q6-aot-runtime`; main is `84b1c2cb`.

## Result

With a precompiled runtime, `pystachy build` of the 33 timed programs took 46.5 s instead of
80.7 s (geometric mean 2.84 times faster). The 24 programs that built in under 2.1 s on main built
2.42 to 6.35 times faster (geometric mean 3.35): `print(1)` in 0.115 s instead of 0.318 s, nbody
in 0.236 s instead of 1.040 s. Programs whose own code dominates the build gain less: the
import-heavy program built in 5.48 s instead of 7.18 s, `bm_logging` in 10.55 s instead of
12.86 s. The full AOT test corpus ran in 414 s instead of 857 s with four workers, every case
passing in both.

Execution cost did not change on aggregate: the executables executed a geometric mean of 0.4%
more instructions, 26 of 33 within 2%, and their minimum wall times were a geometric mean of 0.1%
lower. Executables grew by a geometric mean of 31% (median 35.7 KiB), because a runtime
compiled once keeps code that one program never reaches. The first build after a new runtime
pays about 5 s once to make the precompiled runtime.

Measured on an idle 4-vCPU x86-64 VM, Ubuntu 24.04, LLVM 18.1.3, CPython 3.13.18; builds and
runs pinned to one CPU and interleaved between the compilers (`scripts/perfab.py`); instructions
counted with callgrind (`scripts/cgab.py`). Per program: `raw/perfab-table.md`.

## Where an AOT build spent its time on main

`pystachy build bench/nbody.py` on main, warm runtime cache, pinned to one CPU
(`raw/aot-stage-profile-main.txt`): 1.07 to 1.13 s, of which `-O2` took 0.46 to 0.50 s and
code generation 0.45 to 0.50 s. The program's own IR is 843 lines; `llvm-link --only-needed`
with the runtime makes a module of 26,750 lines and 134 functions, 9 of them the program's.
Almost all of the build optimized and compiled runtime code again.

## What the program needs from the runtime's bodies

Main's AOT pipeline was run over 352 programs (the benchmarks and every sixth case of
`tests/programs`) with `-Rpass=inline` on its optimization step (`scripts/run_corpus.sh`,
`scripts/clang-inline-remarks.sh`, `scripts/analyze.py`). LLVM inlined 275 distinct runtime
functions into program code (`raw/inlined-runtime-functions.txt`). Most are small; the large
ones are inlined where a constant argument selects one case: `pys_mpz_binop` (909
instructions), `pys_big_op` (477), `pys_dyn_list_method` (440) and `pys_set_cmp` (261) switch
on such an argument, and `pys_str_float` (902) was inlined where a constant float was
formatted.

The interface therefore keeps the bodies of functions of up to 200 instructions, of functions
that switch on a parameter (10 functions, 4,787 instructions, at main) and of `alwaysinline`
ones. Of the 275 functions, it keeps 274; only `pys_str_float` loses its body
(`raw/inlined-but-declared.txt`). Optimizing nbody against interfaces of growing size
(`raw/body-budget-nbody.txt`) took 0.04 s with no bodies, 0.07 s up to 200 instructions and
0.35 to 0.41 s with every body.

## Validation

All on `c739499c` (`raw/validation-pr.txt`):

| Check | Result |
|---|---|
| `make` bootstrap | fixed point; 257 to 279 s over the PR's last four builds (main 259 s) |
| `tests/run.sh ./pystachy aot`, every case | 4,595 passed, 0 failed, 414 s (main: 4,595 passed, 857 s) |
| UBSan (`-fsanitize=undefined`), GC stress (`PYSTACHY_GC_STRESS_PROGRAM=1`) and JIT slices of 506 cases | all passed; no `.fail` marker under UBSan |
| `make test-cache` (native, hosted) | 95 and 97 passed, 0 failed |
| `tools/aotprobe.py` (native, hosted) | passed |
| `tools/test_runtime_*.py` | 93 run, 8 skipped, 0 failed |
| `tools/test_bootstrap_tier.py`, `test_compiler_state_timing.py`, `test_retained_ir.py` | passed |
| ruff, shellcheck, mypy, `clang -Wall -Wextra -Werror runtime.c`, `check_runtime.py` | passed |

Not run locally: the full `make verify` matrix, ASan configurations (which keep the old path),
macOS (`-dead_strip`), AArch64 and LLVM other than 18.

The instruction counts found a bug in the first version (`ec408fe0`): the late module, which
should bring back `pys_new`'s body for allocelide's late step, was empty, so programs whose
allocations survived `-O2` called the allocator's fast path out of line (chaos +6.1%, float
+4.0% instructions; `raw/callgrind-before-late-fix.txt`). `c739499c` fixed it, and
`tools/aotprobe.py` now requires that no call of `pys_new` is left after the late step.

## Limits

- Executables are larger: `print(1)` 47,232 to 93,848 bytes. Main's per-program `-O2` could
  prove, for example, that a program which opens no file leaves the collector's file table
  empty, and dropped the code that closes and reports files, with the string `repr` and
  Unicode tables it reaches. The precompiled runtime keeps what any program might reach from the
  functions this one calls.
- Some runtime helpers are no longer inlined where main's per-program module had left them a
  single caller: nqueens executes 4.4% more instructions (`sadd` and `lelem` are calls inside
  the inlined `pys_set_update_list`), generators 3.9%, micro_words 2.5%; comprehensions executes
  5.1% fewer and raytrace 2.1% fewer. `print(1)` executes 43,000 more instructions at start-up
  (dynamic symbol lookups for more libc functions).
- `pys_str_float` is no longer inlined where a constant float is formatted (4 of 352 programs).
- Median wall times varied by up to 14% for one program between passes on this host while its
  instruction count did not; `micro_fib` ran 4 to 5% slower in every pass with identical code
  for `fib` at a different address and equal instruction counts.

## Files

- `scripts/perfab.py`: paired build and run timing of two compilers (`hello.py`, `imports.py`
  and the 31 programs of the parent report's timing set); `scripts/cgab.py`: their instruction
  counts.
- `scripts/run_corpus.sh`, `scripts/clang-inline-remarks.sh`, `scripts/analyze.py`: the
  inlining census.
- `raw/`: measurements and logs named in the text; `*-before-late-fix.*` are of `ec408fe0`.
