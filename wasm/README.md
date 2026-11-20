# WebAssembly (experimental)

This directory builds Pystachy programs for `wasm32-wasi` (WASI preview 1) and runs them
under Node's WASI. Programs compile through LLVM. The runtime (`runtime.c` and `runtime.py`)
compiles once for the same target.

## Build and run

The toolchain is the LLVM 18 that the native build uses, plus Ubuntu's `wasi-libc` and
`libclang-rt-18-dev-wasm32` packages (or `WASI_SYSROOT`), and Node 22 or later.

```sh
make                                     # the native compiler, which emits the IR
wasm/build.sh runtime                    # build/wasm/runtime.o and stubs.o, once
wasm/build.sh program prog.py prog.wasm  # the program's IR, compiled and linked
node --disable-warning=ExperimentalWarning wasm/run.mjs prog.wasm ARGS...
tests/run.sh ./pystachy wasm tests/programs/apps/ouro2_*.py   # the corpus's wasm mode
```

Node 22.23 (V8 12.4) crashed with SIGSEGV in its optimized fast calls of WASI functions: every
time after a program wrote 48 files of 1 MiB buffers (`io_dropped_buffers`), and now and then
under load, about ten programs per corpus run. `run.mjs` turns those fast calls off
(`--no-turbo-fast-api-calls`), after which no run crashed.

`wasm/build.sh program` runs `pystachy ir`, adapts the IR to wasm32 (`wasm32_ir.py`),
compiles it with `clang --target=wasm32-wasi -O2` and links it with `wasm-ld` against the
runtime. The link treats a signature mismatch as an error, because a mismatched call traps.

## What differs from a native build

- **The collector is off.** The conservative stack scan cannot see WebAssembly locals, so
  `runtime.c` sets `PYSTACHY_GC=off` under WASI. The engine caps memory (4 GiB for wasm32).
- **A raise ends the program.** `llc` lowers each `invoke` to a call, and the unwinder stubs
  (`wasi_stubs.c`) never find a handler. An uncaught exception prints CPython's last line and
  exit status, but `try`, `with` and `except` cannot catch anything.
- **No processes, signals, users or dynamic loading.** `wasi_stubs.c` defines those calls to
  fail with `ENOSYS`, so the runtime raises the matching `OSError`.
- **The file system is the host's**, through a preopened `/`. The working directory is Node's,
  passed as `PWD`.
- **Pointers are 4 bytes.** Compiled code addresses the runtime's structs through their LLVM
  types, which follow the target's layout. Constants that hold an address in a 64-bit slot are
  rewritten as the address and a zero word (`wasm32_ir.py`). Dynamic class dispatch and
  reflection read the name, class id and flags at their target-specific offsets in `DynType`
  and the flags in a class reflection record.
  A boxed class record pointer occupies an eight-byte payload slot on both targets.

## Files

| File | Purpose |
|---|---|
| `build.sh` | Runtime and program builds |
| `run.mjs` | Node WASI runner |
| `wasm32_ir.py` | IR rewrite for wasm32 constants, `main` and C library lengths |
| `wasi_stubs.c` | Missing POSIX functions, unwinder stubs, working directory |
| `include/` | Headers that `wasi-libc` lacks (`dlfcn.h`, `pthread.h`, `pwd.h`, `sys/wait.h`) and declarations `runtime.c` needs (`pystachy_wasi.h`) |
