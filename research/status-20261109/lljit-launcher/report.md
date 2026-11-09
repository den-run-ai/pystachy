# In-process LLJIT launcher instead of `lli`: prototype evaluation

Copied here from the agent's local branch: the prototype is in [prototype/](prototype/), its
measurements in [results/](results/) and the -O0 reproducer in [o0/](o0/); the scratchpad
paths below are where they were produced.

Refs #707, #430. Evaluated 2026-11-09 on main `56678df4` (Ubuntu 24.04 x86-64, LLVM 18.1.3,
CPython 3.13.18; shared 4-vCPU container; timings pinned to one CPU while both heavy slots
were held). Branch `claude/happy-franklin-mc6j4c-lljit-launcher`, commits `2cc3be4a`,
`433b5209`, `fd5bee37` (head `fd5bee37b3479349617dbf760f0068eccdb137ae`), prototype in
`research/lljit-launcher/`. Evidence: `<scratchpad>/lljit.hjA6mG/` (`logs/`, harnesses,
`*-results.json`, `o0/` reproducer), where `<scratchpad>` is
`/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad`.

## TL;DR

**Recommendation: do it later under #707, not now.** Retire MCJIT with the `llc -O0` +
`lli` ORC change (nothing new to build), fix the -O0 miscompile below first whichever route
is used, and keep this launcher as the start of #707's in-process driver.

- **New finding, not caused by the launcher:** -O0 code generation silently miscompiles
  values that flow into a landing pad (LLVM 18, 20 and 23). `PYSTACHY_JIT_CODEGEN=0` on main
  (MCJIT -O0), `llc -O0` + lli and the launcher at -O0 all fail
  `tests/programs/apps/port_json_repair_bounds.py`; an 11-line program returns a stack
  address instead of `-2`. -O1/-O2 are correct.
- **The launcher works:** 231 lines of C on LLJIT's C API, driven through the driver's
  unchanged launch path: all 2,369 JIT programs and deviations pass at -O2 (2,387/2,387
  checks) and at -O0 except that case; GC stress, FFI/embedding and jitfdprobe pass.
- **Speed:** -O0 runs `print(1)` in 29 ms and import-heavy in 733 ms, against 55/796 ms for
  `llc -O0` + lli and 30/813 ms for MCJIT -O0; at -O2 it equals lli (1,601 vs 1,593 ms) but
  starts 4-5 ms sooner. Against today's ORC default, -O0 halves import-heavy: #430's call.
- **Cost:** a compiled launcher per LLVM major (built at `make` or first use: header-free and
  0.5 s on Ubuntu, unverified on macOS's provisioned LLVM), an `lli` fallback that keeps
  `jit_handoff` and doubles the JIT launch matrix, and an Orc C API that LLVM marks unstable
  and that changed twice between 18 and 23. Its gain over the llc route (25 ms; 8-11% on
  large programs) does not pay for that alone. With -O0 code generation, `opt` becomes the
  largest step (41% of `print(1)`, a third of import-heavy): folding it into the same
  process is the measurement #707 needs before adopting.

## What was built

`research/lljit-launcher/pystachy-lljit.c` (LLVM C API) accepts the lli command line that
`pystachy run` builds (`-profile-guided-section-prefix=false`, `-dlopen=`, `-extra-object=`,
`-extra-archive=`, `-jit-kind=`, the `/dev/fd/N` input, program arguments) plus `-O0..-O3`,
and runs the program as LLVM 18's lli ORC path does: `-dlopen` first (RTLD_GLOBAL), LLJIT
with JITLink (confirmed: `ObjectLinkingLayer::emit`, not RuntimeDyld) and the process's
symbols, then the module, archives, objects; `llvm.global_ctors` in priority order before
`main(argc, argv, envp)` and `llvm.global_dtors` after it returns; `argv[0]` is the input's
name; `main`'s result is the exit status. Unlike lli: `-O` is honoured; no LLVM signal
handlers, stack printer, GDB registration or perf listener; no JIT teardown before `exit`.
The C API has no `LLJIT::initialize`, so each constructor list is collected into one
function before the module is added (what the generic IR platform does internally). Error
text mirrors lli's (`JIT session error: Symbols not found: [ x ]`, status 1).

Also: `llvm-c-decls.h` (the C API declarations it uses: builds with no LLVM headers),
`build.sh [--no-headers]`, `mkwrap.sh` (a `PYSTACHY_LLVM` directory whose `lli` execs the
launcher, so descriptor inputs, `PYSTACHY_JIT_HANDOFF` and `jit_handoff` run unchanged),
`pystachy-lljit.cpp` (the same launcher on the C++ API) and a README. `research/` is
git-ignored and rejected by `make check-repository`: a research branch, force-added.

## Correctness

Through the real driver (`./pystachy run` built from `56678df4`, `PYSTACHY_PROGRAM_CACHE=0`,
private `PYSTACHY_CACHE`), `lli` replaced by the launcher:

| Check | Launcher -O2 | Launcher -O0 |
|---|---|---|
| Every JIT case: all `tests/programs` + `tests/deviations` (2,369 cases) | 2,387/2,387 | 2,386/2,387 (see below) |
| Sample: all 137 `exceptions`, 130 `deviations`, 73 `io`, every SIGINT/KeyboardInterrupt, `sys.exit`, `.in` stdin and closed-stream case (376) | 376/376 | 376/376 |
| GC stress `PYSTACHY_GC_STRESS_PROGRAM=1`, every 20th program (112 cases, 19 areas) | 113/113 | 113/113 |
| `tests/ffi/run.sh ./pystachy jit`: C externs, embedding (libpython `-dlopen`, `pyembed.o` `-extra-object`), GC stress 7, ext modules | 147/147 | not run |
| `tools/jitfdprobe.py`: descriptors, SIGINT dispositions, closed streams, shared/object runtimes, MCJIT flags (= launcher -O0), embedding, cleanup | 25/25 | (in the same run) |
| Hosted compiler (`python3.13 pystachy.py run`): `print(1)`, `exc_finally_nested` | match | match |

jitfdprobe ran with `lli` a symlink to the launcher and the compiler given as
`env ./pystachy`, which skips its native program-cache section: that section never runs
`lli` and bypasses any wrapper `PYSTACHY_LLVM` ("undeclared tool wrapper", "toolchain search
layout unavailable"), so it cannot run in this setup. Negative control: without the
driver's `-profile-guided-section-prefix=false`, `tests/programs/inference/dynany_jit_try.py`
fails under lli and under the launcher at -O2 (passes at -O0): the JITLink landing-pad
problem is the same, the flag is still needed, and the launcher forwards LLVM options.
The same source built against libLLVM 20.1.8 and 23.1.6 runs the LLVM-18 bitcode of
import-heavy and regex_effbot with CPython's output at -O0 and -O2.

## Pre-existing -O0 miscompile (all -O0 routes)

`port_json_repair_bounds` (jit) prints `AssertionError` at -O0. Reproduced with
`tests/run.sh`: launcher -O0 fails, launcher -O2 and lli ORC pass, `llc -O0` + lli fails, and
main's own `PYSTACHY_JIT_CODEGEN=0` (MCJIT -O0) fails. Minimal program
(`<scratchpad>/lljit.hjA6mG/o0/min.py`):

```python
def skip(text: str, index: int) -> int:
    try:
        char = text[index]
        while char.isspace():
            index += 1
            char = text[index]
    except IndexError:
        pass
    return index
print(skip("", -2), skip(" ", 0), skip("a", 0))   # CPython: -2 1 0
```

-O0 prints a stack address and two zeros (e.g. `140720487789648 0 0`; MCJIT -O0, launcher
-O0, and the launcher on LLVM 20 and 23, C and C++ API alike); -O1 and -O2 print `-2 1 0`. Mechanism (`llc -O0
-print-after=phi-node-elimination` on the captured IR, `o0/min.ll`): the landing pad's
`phi [%a1, entry], [%t22, L25]` is identical to the loop header's PHI, so PHI elimination
reuses that PHI's incoming copies, which sit after the call on the normal path (after
`EH_LABEL .Ltmp1`/`.Ltmp3`). On the exceptional path the slot holds the previous value, or
nothing on the first call. The IR is valid; this looks like an LLVM bug in PHIElimination's
reuse of identical PHIs (its comment says this "only happens for critical edges"), reached
because Pystachy feeds mem2reg'd IR to -O0 code generation, which clang -O0 never does.
Work-arounds measured on the launcher: `-O1` is correct but generates code as slowly as -O2
(import-heavy 1,003 vs 1,021 ms); `opt -passes=reg2mem` on the whole module is correct but
code generation grows from 169 to 314 ms (regex 20: 647 -> 853 ms). A targeted fix
(demote only landing-pad PHIs, or keep them from duplicating a normal successor's PHI) and an
upstream report are needed before any -O0 route is trusted or made a default.

## Measurements

All under `timing.sh`, `taskset -c 2`, variants interleaved, outputs checked against CPython
before and during timing; medians [min-max].

**End-to-end `pystachy run`** (warm runtime cache, program cache off, 7 rounds,
`bench.py`). "llc -O0" is the test wrapper (`llc -O0`, an `llvm-as` stub, `lli
-extra-object`, as in the brief's table), not the orc-codegen driver code, which skips the
bash and `llvm-as` steps and may be a few ms faster.

| ms | lli ORC (default) | lli MCJIT -O0 | llc -O0 + lli ORC | launcher -O0 | launcher -O2 |
|---|---:|---:|---:|---:|---:|
| `print(1)` | 33.9 [33-35] | 29.8 [28-33] | 54.5 [50-70] | **29.1** [26-33] | 30.3 [29-35] |
| import-heavy | 1,593 [1530-1735] | 813 [769-862] | 796 [747-870] | **733** [668-861] | 1,601 [1556-1644] |
| regex_effbot, 1 loop | 1,276 [1191-1356] | 675 [621-740] | 670 [596-726] | **608** [554-638] | 1,270 [1170-1353] |
| regex_effbot, 20 loops | 1,531 [1456-1578] | 1,140 [1107-1321] | 1,186 [1034-1285] | **1,053** [1044-1165] | 1,479 [1458-1598] |

Peak RSS (wait4 `ru_maxrss`, whole run): 60 MB for `print(1)` everywhere; -O2 code generation
costs 1-7 MB more than -O0 (regex 20: 109-110 vs 103-105 MB); llc -O0 peaks at 89 MB there
because its code generation runs in another process.

**Same inputs, process only** (the bitcode and shared runtime the driver handed lli,
captured once; `phases.py`, 7 rounds), isolating lli from the launcher:

| ms | lli ORC | lli MCJIT -O0 | launcher -O0 | launcher -O2 | launcher code generation -O0 / -O2 |
|---|---:|---:|---:|---:|---:|
| `print(1)` | 19.9 [18-21] | 14.2 [13-15] | 13.6 [13-14] | 15.7 [15-17] | 1.5 / 3.6 |
| import-heavy | 1,051 [997-1175] | 325 [299-367] | 216 [191-301] | 1,109 [989-1215] | 169 / 1,064 |
| regex_effbot 1 | 881 [810-944] | 260 [240-306] | 190 [170-252] | 850 [788-946] | 122 / 798 |
| regex_effbot 20 | 1,095 [1038-1178] | 733 [691-792] | 674 [651-702] | 1,108 [1010-1142] | 134 / 841 |

Bitcode parsing takes 22-28 ms of these. On regex 20, `main` runs 494 ms at -O0 against
221 ms at -O2: -O0 code is 2.2x slower, but 700 ms of code generation is saved.

**Start-up with an empty `main`** (`startup.py`, 30 rounds; `optstart.py` for the tools):

| ms | median [range] |
|---|---:|
| empty C program / the same linked with libLLVM-18 | 2.0 [1.8-2.6] / 8.6 [7.6-16.6] |
| lli ORC / lli MCJIT | 15.0 [13.1-27.5] / 11.1 [9.8-18.5] |
| launcher -O0 / -O2 (C API, shared libLLVM) | 10.2 [8.9-20.6] / 10.7 [9.5-18.8] |
| launcher statically linked (32 MB, 15 s link) -O0 / -O2 | 6.1 [5.6-9.3] / 6.5 [5.9-9.5] |
| launcher on the C++ API -O0 / -O2 | 11.1 [9.9-22.0] / 14.0 [12.2-19.8] |
| `opt` on an empty module / `llc -O0` on one (separate session) | 13.2 [11.1-17.0] / 13.9 [11.7-17.7] |

Loading libLLVM.so.18.1 costs about 6.6 ms; the launcher's own work beyond it is 1.6 ms
against lli's 6.4 ms. For an empty `main`, lli and the C++ variant compile three IR modules
(the program and the generic IR platform's two support modules, materialized by
`initialize`/`deinitialize`), the C launcher one (gdb breakpoint on `IRCompileLayer::emit`).

**Where a launcher -O0 run goes** (`PYSTACHY_TIMING=1` and `-trace`, `stages.py`, 5 rounds):

| ms | wall | frontend | `opt` | launcher: bitcode parse | code generation | `main` |
|---|---:|---:|---:|---:|---:|---:|
| `print(1)` | 30.1 | 0.4 | 12.3 | 0.3 | 1.6 | 0.4 |
| import-heavy | 727 | 244 | 240 | 28 | 163 | 1.5 |
| regex_effbot 1 | 583 | 179 | 193 | 22 | 123 | 28 |

**Reading.** At equal code-generation level the launcher equals lli within noise on large
modules and starts 4-5 ms sooner. Its gains come from -O0 without MCJIT or an extra process:
against the llc wrapper 25 ms on `print(1)` and 60-130 ms (8-11%) on the others; against
MCJIT -O0 0-90 ms (0-10%). Against today's default the code-generation policy (#430) is
what matters: -O0 cuts import-heavy by 54%, regex 1 by 52%, regex 20 by 31% (once the
miscompile is fixed). With -O0, `opt` is the next target.

## Integration assessment

**Build-time headers.** Neither Ubuntu's `llvm-18` nor the GitHub-install provisioner
(`pystachy_toolchain.py`'s `.deb`s) installs headers; `llvm-18-dev` is 329 MB installed
(28 MB C++ headers, 456 KB `llvm-c`, the rest static libraries). The C API removes the
need: `build.sh --no-headers` compiles against `llvm-c-decls.h` alone and links the
`libLLVM.so.N.1` that `lli` loads (`ldd lli`; `libllvm18` provides it). Verified for
18.1.3, 20.1.8 and 23.1.6 here; a build takes about 0.5 s. The C++ API needs the dev
headers and a C++ toolchain.

**API skew.** The C++ launcher (99 lines: `LLJITBuilder`, `initialize`/`deinitialize`,
`linkStaticLibraryInto`) compiled unchanged against 18, 20 and 23 and ran on all three. The
C launcher needed two gates, both at LLVM 21: 21 removed `LLVMOrcThreadSafeContextGetContext`
(use `...FromLLVMContext`), and 18-20 define `LLVMOrcCreateStaticLibrarySearchGeneratorForPath`
without the header's triple parameter, hence with C++ linkage: `nm -D` shows only
`_Z48LLVMOrcCreateStatic...` in 18.1.3 and 20.1.8 (the prototype binds the mangled name); 21's
header drops the parameter (source), and 22.1.8/23.1.6 export the C name. `llvm-c/Orc.h` and
`LLJIT.h` both say "experimental... *NOT* stable". For this surface the C API is not more
stable than C++; it wins on header-free builds and plain C. Either binary is tied to one
libLLVM major and must be rebuilt per LLVM version: it belongs in the per-toolchain cache.

**How each install would get it.**
- Source checkout and release packages (`make`): build with the toolchain's clang beside the
  runtime; header-free on Ubuntu (`llvm-18` depends on libllvm18); Homebrew `llvm@20` ships
  `libLLVM.dylib` and headers (not tried: no macOS here).
- Hosted (`python3 pystachy.py run`) and GitHub pip/uv installs (pure Python, C sources as
  package data): compile `pystachy-lljit.c` at first use and cache it like `runtime-*.so`,
  keyed by LLVM version and libLLVM identity, with an `lli` fallback. Ubuntu's provisioned
  `.deb`s suffice. The macOS provisioner unpacks upstream LLVM 20.1.8, whose tools "link only
  system libraries": whether that archive has a `libLLVM.dylib` is unverified; otherwise a
  static link of its `lib/*.a` or the `lli` fallback. Docker is Ubuntu.
- macOS also depends on LLVM 20's compact-unwind registration for JIT'd exceptions; the
  launcher uses lli's LLJIT defaults but is untested there.
- Who still runs `lli` at all: on Linux the native CLI's default program cache replaces it
  (a miss builds and runs an executable); `lli` serves hosted and pip/uv installs, macOS (no
  program cache), `PYSTACHY_JIT_CODEGEN=0`, CPython embedding, external native libraries and
  cache-off runs (docs/program-cache.md).

**What the driver and runtime could drop** (driver.py ~1142-1201, runtime.c ~6612-6700):
- with either MCJIT replacement: `-jit-kind=mcjit`, the private `JITDUMPDIR`, the handoff's
  DIR field and `jitdump_remove` (the orc-codegen branch drops these too);
- against the llc route, the launcher needs no `llc` process, temporary object or stub main
  module (`OBJHOOKS_MAIN`): `-O` is a flag;
- only if `lli` goes entirely (no fallback): `jit_handoff`'s signal restoration and the
  ignored-signal plumbing (`ignored_signals`, `pys_ignored_signals`), since the launcher
  installs no handlers. Closing the input descriptors could move into the launcher;
  `PYSTACHY_ARGV0` stays (the runtime keys `RTLD_DEEPBIND` for `ffi.extern` on it: libLLVM's
  dependencies are in the launcher's global scope as in lli's). With a fallback, nothing in
  `jit_handoff` can go.

**Risks.** Two launch paths in CI if `lli` stays as fallback; the unstable Orc C API; the
generic IR platform still interposes `atexit` for JIT'd code and the launcher never runs
those handlers (lli runs them after `main` returns; Pystachy emits no such call today); no
GDB JIT registration (`LLVMOrcLLJITEnableDebugSupport` could restore it); a first-use build
step (~0.5 s) that can fail; macOS unverified; the -O0 miscompile above.

## Recommendation

**Do it later under #707.** Now: retire MCJIT with the `llc -O0` route, which is no worse
than MCJIT -O0 (same miscompile) and builds nothing; file the -O0 miscompile with the
reproducer and fix or work around it before any -O0 route is trusted or made a default.
Under #707, grow this prototype and adopt it when:

1. it also runs `opt`'s JIT pipeline in-process (`LLVMRunPasses` takes the same pass string)
   on the textual IR, and that measures clearly better than `opt` + launcher;
2. macOS works with the provisioned LLVM 20.1.8 and with Homebrew `llvm@20`, exceptions included;
3. the fallback policy is decided (keep `lli` tested, or require the launcher where `run` works);
4. its build is part of the toolchain cache contract, like `runtime-*.so`.

Not reject: it is small, correct on everything run, and the only route to per-run code
generation control without MCJIT or an extra process. Not now: against the llc route it
saves 25 ms on `print(1)` and 8-11% on larger programs, for a new build artifact and launch path.

## Validation commands

From `/home/user/wt/lljit-launcher`, `D=<scratchpad>/lljit.hjA6mG`, `. $D/env.sh` (strips
`PYSTACHY_*`; sets `PYSTACHY_LLVM=$D/wrap/bin`, `PYSTACHY_PROGRAM_CACHE=0`, a private
`PYSTACHY_CACHE`, `PYSTACHY_JOBS=2`); heavy steps through `heavy.sh`, timings through `timing.sh`.

- `apt-get -o DPkg::Lock::Timeout=900 install -y --no-install-recommends llvm-18-dev`, then
  `llvm-20-dev llvm-23-dev` (the installed libllvm20/23 versions; nothing upgraded or removed);
  `clang --version` and `/usr/lib/llvm-18/bin/lli --version` still report 18.1.3.
- `make`: fixed points pass (3 min 9 s).
- `research/lljit-launcher/build.sh [--no-headers] OUT /usr/lib/llvm-{18,20,23}/bin`: six
  builds; each matches lli on a constructor/destructor/argv/status module and `-extra-archive`.
- `LLJIT_MODE=lljit LLJIT_OPT={2,0} tests/run.sh ./pystachy jit $(cat $D/fulljit.txt)`:
  2,387 passed / 2,386 passed, 1 failed (`port_json_repair_bounds`, above).
- The same over `$D/sample.txt`: 376 passed at each; with `PYSTACHY_GC_STRESS_PROGRAM=1` over
  `$D/gcsample.txt`: 113 passed at each.
- `PY=python3.13 tests/ffi/run.sh ./pystachy jit` (-O2): 147 passed, 0 failed.
- `python3.13 tools/jitfdprobe.py -c "native=env ./pystachy"` with `PYSTACHY_LLVM=$D/wrapelf/bin`
  (`lli` -> launcher): 25 checks passed.
- `$D/repro.sh`, `$D/negctl.sh`: the -O0 and section-prefix controls above.
- `make -k check-fast lint` (devenv first on `PATH`): ruff, mypy (55 files), runtime roots,
  shellcheck and `clang -Wall -Wextra -Werror` pass; `check-repository` fails on `research/`
  by design, so make skipped check-fast's unit tests (no file they cover changed).
- `bench.py 7`, `phases.py 7`, `startup.py 30`, `stages.py 5`, `optstart.py 30`, `levels.py 5`,
  `r2m.py`: tables and figures above (`$D/*-results.json`).

## Not run, limits and open questions

- macOS and Linux ARM64 (not available); hosted path beyond two programs; `make verify`, CI,
  `make irsame` (no compiler change); FFI tests at -O0.
- Shared host: other agents' jobs ran on the other CPUs; launcher-vs-lli differences under
  6% at -O2 on large modules are noise.
- The llc column is the bash test wrapper, not orc-codegen's driver change.
- Not tried: lazy (per-function) compilation, an object cache, concurrent compilation,
  `LLVMOrcLLJITEnableDebugSupport`, `-O3`.
- Open: is the PHIElimination reuse already reported or fixed upstream (not checked)? What
  does a targeted landing-pad-PHI workaround cost?
