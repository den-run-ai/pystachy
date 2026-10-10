# FFI research for Pystachy: paused state (2026-10-10)

**The question:** "Propose best ffi mechanism for pystachy following latest compiler, runtime,
interop best practices with minimal impact that could maybe work with cpython bidirectionally.
Only recommend, jit or aot or both."

**Status:** research done, recommendation drafted and adversarially reviewed, final revision
interrupted. Nothing on `main` was changed. This branch only adds `research/ffi/`.

## Where things stand

| step | state | saved here |
|---|---|---|
| Stage 1: 8 agents (repo ABI map, documented constraints, CPython C API 2026, peer compilers, LLVM JIT/AOT, GC interop, 2 prototypes) | done | `stage1/digest.txt` (summaries and implications), `stage1/full.json` (all findings with evidence and open questions) |
| Stage 2: 3 designs (minimal-impact, contract-first, state-of-the-art) | done | `stage2/proposals.json` |
| Stage 2: 2 verifiers (C API facts; LLVM and prototype reproduction) | done | `stage2/verifications.json` |
| Stage 2: 2 judges (maintainer, interop veteran) | done: both picked **minimal-impact** (36 and 39 against contract-first 34/35 and state-of-the-art 28/31) | `stage2/judgments.json` |
| Synthesis, with a working prototype of all three stages | done | `stage2/synthesis_draft.json`, `prototype/tree2-tested.patch` |
| Refuter | done: 4 blocking issues | `stage2/refutation.json` |
| Revision for those issues | **interrupted**: fixes 1-4 done, step 5 (nonblocking fixes, full verification rerun) not finished | `prototype/tree3-revision-wip.patch` (untested) |
| Final answer to the user | **not delivered yet** | |

## The draft recommendation, in short

One mechanism, in stacked stages that each merge on their own. Programs that don't use it keep
byte-identical IR. No Python.h, no new toolchain, runtime.py untouched, runtime.c stays libc-only
and free of thread-local storage.

- **Pystachy calls C: both JIT and AOT.** `@ffi.extern("lib")` on a typed `...` stub, with every C
  integer at an explicit width. Its ctypes twin in `tools/rt_cpython/ffi.py` lets the same file run
  under CPython, which keeps CPython as the oracle. JIT: `lli -dlopen=<lib>` (pystachy.py:16670).
  AOT: `-l:<soname>` on the link (16653).
- **Pystachy calls CPython: both JIT and AOT.** `lib/pyobj.py` is plain subset code that calls
  the CPython stable ABI through the same `@extern`, with a plain-Python twin. JIT: `lli
  -dlopen=libpython`. AOT: link libpython. A 9-line `pyembed.c` finalizes CPython at exit.
- **CPython calls Pystachy: AOT only.** `pystachy ext` builds an abi3 module (CPython 3.12+, GIL
  builds) or an abi3t one (3.15+, GIL and free-threaded, PEP 803/793/820), both from identical
  program IR. Public functions are marked `@ffi.export`, the glue is a header-free `pyext.c`, and
  every entry point has a catch-all landing pad. About 21-24 ns per call, against about 250 ns
  through ctypes.
- **Not recommended:**
  - a JIT inside the CPython process (it works through ctypes and libLLVM's ORC, but costs a
    117-123 MB libLLVM, uses an unstable C API, and adds about 56 MiB of RSS);
  - letting exceptions unwind through CPython frames (that leaks one reference per crossing and
    gives RecursionError after about 1000 crossings);
  - HPy, PyNI or PEP 809;
  - header importers;
  - the typed-IR §7.4 lowering now (it is blocked on step 16).
- **Later stages:** a wider boundary (lists, dicts, keywords), a compile-on-import cache (still AOT,
  like `mojo.importer`), then callbacks, opaque handles and pins once M3 lands.
- **Prototype measurements (tree2):**
  - size: pystachy.py +226/−17, runtime.c +37/−1, 895 new lines;
  - `make` reaches the fixed point;
  - tests/run.sh: 1886/1886 pass;
  - irsame: 1265/1265 identical;
  - probes match CPython on 3.12, 3.13, 3.14, 3.15.0 and 3.15.0t, under GC stress and UBSan.

The full draft is `stage2/synthesis_draft.json`: stages S0 to S6, the changes by file:line, the
deviations to document, and the open decisions for the maintainer.

## The refuter's 4 blocking issues (fixed in tree3, not yet re-verified)

1. In ext mode, `__name__`, sys.argv, print failure and re-exec after failure behave as in a
   standalone program, so the .so diverges from its own source.
2. Exported functions can't be pickled, because `fn.__self__` is an int. The fix makes self the
   module and adds per-export trampolines.
3. Automatic Py_DecRef draining is unsafe under nested Py→Pys→Py→Pys re-entry. The fix drains
   only at depth 1.
4. A builtin `ffi` module breaks programs that ship their own `ffi.py`. The fix lets the program's
   own module shadow it.

## How to resume

1. Apply the WIP revision to a scratch copy, not to main:
   `git worktree add ../pys-ffi main && cd ../pys-ffi && git apply ../pystachy/research/ffi/prototype/tree3-revision-wip.patch`
   If it fails, use `tree2-tested.patch`, which is the verified state.
2. Finish step 5: the nonblocking items in `stage2/refutation.json`. Then rerun `make`,
   `tests/run.sh ./pystachy`, `make irsame REF=main`, and `prototype/probe.sh` / `all.sh` (they
   use the old scratch paths; edit `SCRATCH`). The probes on 3.12, 3.14 and 3.15(t) need
   python-build-standalone builds again: they were downloaded to scratch and are not saved.
3. Re-run a refuter on the revised draft. `workflows/stage2-design.js` holds the prompts and
   schemas; change its `S` path, and feed it the saved JSON instead of re-running stage 1.
4. Deliver the final recommendation (JIT/AOT per direction) to the user. Optionally publish it as
   the decision record that issue #4 §4 asks for (stage S0: docs/ffi.md).

## Files

- `stage1/`, `stage2/`: the agents' structured results.
- `prototype/`:
  - `tree2-tested.patch`: the verified prototype;
  - `tree3-revision-wip.patch`: the revision, untested;
  - `final-*.diff`;
  - the probe scripts and logs;
  - `abi_check.py`.
- `scratch/`: the spikes' own sources and logs:
  - spike_ext: Python→Pystachy extension;
  - spike_embed: Pystachy→Python, both tiers, and the in-process ORC JIT;
  - web-capi/exp: pure-IR abi3t modules;
  - web-gc and web-llvm experiments;
  - repo-abi: GC-stress repros;
  - stage2: the per-agent working directories.

  Third-party checkouts, binaries and repo copies are left out.
- `workflows/`: the two workflow scripts.
