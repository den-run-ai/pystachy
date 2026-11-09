# LLVM 20, 22 and 23 against 18: compatibility and performance

An agent evaluated Ubuntu's LLVM 18.1.3 against apt.llvm.org's 20.1.8, 22.1.8 and 23.1.6 on
main `56678df4` (x86-64, shared 4-vCPU host, timings pinned to one CPU with variants
interleaved and outputs checked against CPython). It could not write files of its own; this is
its report, with the coordinator's checks marked. Tables: [summary-tables.txt](summary-tables.txt);
raw results, logs, scripts and reproducers beside it.

## Recommendation

Do not move Linux to LLVM 20 or 22. If upgrading, target 23 on Linux after the generator fix,
keep 18 working, and leave macOS on 20 for now. The gain is 6-16% lower compile cost; generated
code is no faster. Ubuntu 24.04 packages only 18-20 and 26.04 18-22 (default 21), so 23 means
apt.llvm.org or Homebrew (`llvm` is 23.1.5). GitHub's ubuntu-24.04 image has clang 16-18.

## Findings

1. **LLVM 22 and 23 reject every generator.** `llvm.coro.end` now returns `void`
   ([llvm-project#159278](https://github.com/llvm/llvm-project/pull/159278)); the old form
   auto-upgrades only from 24 ([#211081](https://github.com/llvm/llvm-project/pull/211081)). The
   compiler uses generators, so its bootstrap fails too. The fix is two lines
   (`lowering.py:74`, `lower_module.py:611`): either the legacy `declare i1 @llvm.coro.end(ptr, i1)`
   with an unnamed call, which `opt` 18/20/22/23 upgrade to each version's form
   ([coro-opt-matrix/](coro-opt-matrix/); only assertion-enabled 22/23 builds would object), or a
   spelling chosen by LLVM version. *Coordinator check: `opt -passes=verify` 22.1.8 and 23.1.6
   reject today's `declare i1 @llvm.coro.end(ptr, i1, token)`; 18.1.3 and 20.1.8 accept it.*
2. **Silent wrong result on LLVM 20 and 22, Linux AOT:** `math.isnan(math.fmod(nan, 1.0))` is
   False. LLVM marks the `frem` it substitutes for a guarded `fmod` as `nnan` (commit
   `112aac4e8961`; fixed in 23 by `47e6290a3450`). macOS is unaffected (Darwin emits `frem`
   directly). Plain-C reproducer: [fmod/c3.c](fmod/c3.c). Fix: commit `7ba3c1d3` on the local
   branch `claude/happy-franklin-mc6j4c-llvm-versions` adds `no_builtin("fmod")` to `pys_m_fmod`,
   as `no_builtin("pow")` does for `pow` (#656). *Coordinator check: `clang -O2 c3.c` prints 0 with
   20.1.8 and 22.1.8, 1 with 18.1.3 and 23.1.6.*
3. **LLVM 23 deprecates hexadecimal float literals**, to be removed in the next release
   ([release notes](https://releases.llvm.org/23.1.0/docs/ReleaseNotes.html)), so `fbits()` would
   break on 24. A decimal integer with `bitcast (i64 ... to double)` parses identically on 18-23.

## Correctness (22 and 23 with `coro.end` rewritten by a test wrapper)

| Check | 20 | 22 | 23 |
|---|---|---|---|
| 954-case sample, JIT and AOT | 1830/0 | 1830/0 | 1830/0 |
| GC-stress sample, 155 cases | 310/0 | 310/0 | 310/0 |
| `test_stack_floor` | 11/11 | 11/11 | 11/11 |
| try/except and float/math, 43 cases | 85/1 (fmod) | 85/1 (fmod) | 86/0 |

No FMA instructions in 32 AOT executables or any JIT runtime; Pystachy's IR carries no
contraction flags. The LLVM 20 bootstrap reaches both fixed points.

## Timing

Medians in ms, 5 interleaved rounds; LLVM 18 / 20 / 22 / 23.

| | import-heavy | regex_effbot 1 | route |
|---|---|---|---|
| ORC cold JIT | 1765 / 1591 / 1608 / 1488 | 1276 / 1196 / 1205 / 1109 | 1186 / 1140 / 1174 / 1120 |
| `llc -O0` + ORC | 818 / 786 / 767 / 709 | 610 / 596 / 585 / 556 | 580 / 598 / 555 / 523 |
| Program-cache miss | 2200 / 2020 / 2087 / 1883 | 1813 / 1680 / 1734 / 1533 | 1808 / 1628 / 1576 / 1522 |
| AOT build | 6304 / 5878 / 6072 / 5567 | 5235 / 5126 / 4915 / 4470 | 5195 / 4977 / 5091 / 4864 |

Generated code, callgrind instructions on 23 against 18: spectral_norm -11.6%, nbody +9.6%,
json_loads +7.0%, the rest within 2.5%. Timed runs were too noisy to show more.

## JIT and keep-alive notes

- `lli`'s ORC never sets a code-generation level in any release through LLVM main, and already
  uses JITLink. Its `-fast-isel -regalloc=fast` flags reach only 1284 ms (18) and 1137 ms (23) on
  import-heavy, against 705-840 ms for `llc -O0` + ORC.
- MCJIT carries no deprecation markers yet; the 2024 removal
  [RFC](https://discourse.llvm.org/t/rfc-removing-mcjit-and-runtimedyld/80464) waits on LLDB.
- `llvm.fake.use` first ships in LLVM 20 and is best-effort: it held a pointer across a call at
  `-O2`, but was dropped in tail position and at `-O0` in 20; on 18 it becomes a real external
  call. An empty inline-asm keep-alive works on 18-23 at both levels.

## Changed, installed and not run

- Commit `7ba3c1d3` (above): `make` reached both fixed points; `make test` 354/0; a `make test-py`
  subset 6/0; `upstream_math_fmod` passes on 20/22/23; `check-runtime` and `check-fast lint` pass.
- The host gained apt.llvm.org's source list and keyring, and clang/llvm/lld 20, 22 and 23;
  `libllvm20` went from 20.1.2 to 20.1.8. `clang` and LLVM 18 still report 18.1.3.
- Not run: `make verify`, the extra checks on 18, a 22/23 bootstrap, ARM64, macOS and Ubuntu's own
  20.1.2.
