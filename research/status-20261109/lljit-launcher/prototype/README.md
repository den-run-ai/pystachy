# In-process LLJIT launcher (prototype)

Research prototype for [#707](https://github.com/den-run-ai/pystachy/issues/707) and
[#430](https://github.com/den-run-ai/pystachy/issues/430): a small program that runs what
`pystachy run` hands `lli`, built on LLVM's ORC LLJIT through the LLVM C API. It is not wired
into the compiler build, the driver or CI. `research/` is git-ignored and
`make check-repository` rejects it, so this research branch tracks it with `git add -f` and
it cannot reach `main` unnoticed.

| File | Purpose |
|---|---|
| `pystachy-lljit.c` | The launcher: lli's command line as the driver uses it, LLJIT with JITLink |
| `llvm-c-decls.h` | The C API subset it calls, for a build without LLVM headers |
| `build.sh` | `build.sh [--no-headers] OUT [LLVM_BIN_DIR]` (default LLVM 18) |
| `mkwrap.sh` | `mkwrap.sh LAUNCHER DIR [LLVM_BIN_DIR]`: a `PYSTACHY_LLVM` directory whose `lli` runs it |
| `pystachy-lljit.cpp` | The same launcher on the C++ ORC API (`LLJIT::initialize`), for comparison; needs `llvm-N-dev` |

## What it does

It accepts `[-O0|-O1|-O2|-O3] [-dlopen=LIB]... [-extra-object=OBJ]... [-extra-archive=AR]...
[-jit-kind=K] [LLVM-OPTION]... INPUT.bc [ARG]...` and runs the program as LLVM 18's `lli`
ORC path (`runOrcJIT`) does: `-dlopen` libraries first (`RTLD_GLOBAL`), then LLJIT with
JITLink and the process's symbols, the input module, archives, objects; the module's
`llvm.global_ctors` in priority order before `main(argc, argv, envp)` and its
`llvm.global_dtors` after `main` returns; `argv[0]` is the input's name and `main`'s
result is the exit status. Unlike lli it:

- honours `-O` (lli's ORC path generates code at the default level whatever `-O` says);
  the driver's MCJIT mode (`-jit-kind=mcjit -O0`) therefore selects `-O0`;
- installs no LLVM signal handlers, stack printer, GDB registration or perf listener, so
  the program starts with its caller's dispositions and descriptors;
- leaves the JIT mapped at exit instead of tearing it down before the C library's
  `atexit` handlers run.

The C API has no `LLJIT::initialize`, so the launcher collects each constructor list into
one external function before adding the module, as LLJIT's generic IR platform does. Two
C API differences need version gates, both at LLVM 21: it replaced
`LLVMOrcThreadSafeContextGetContext` with `LLVMOrcCreateNewThreadSafeContextFromLLVMContext`,
and LLVM 18-20 define `LLVMOrcCreateStaticLibrarySearchGeneratorForPath` with C++ linkage
(the header's `TargetTriple` parameter is missing from the definition; LLVM 21 changed the
header).

## Try it

```sh
research/lljit-launcher/build.sh /tmp/lljit/pystachy-lljit            # needs llvm-18-dev
research/lljit-launcher/build.sh --no-headers /tmp/lljit/pystachy-lljit # needs only libllvm18
research/lljit-launcher/mkwrap.sh /tmp/lljit/pystachy-lljit /tmp/lljit/bin
PYSTACHY_LLVM=/tmp/lljit/bin PYSTACHY_PROGRAM_CACHE=0 LLJIT_OPT=0 ./pystachy run demo.py
```

Results, measurements and the integration assessment are in the evaluation report that
accompanies this branch; the README describes only the prototype.
