# WebAssembly (experimental)

This directory builds Pystachy programs for `wasm32-wasi` (WASI preview 1) and runs them
under Node's WASI. It is a prototype: the compiler is unchanged, programs reach WebAssembly
through the LLVM IR it already emits, and the runtime (`runtime.c` and `runtime.py`) is
compiled once for the same target.

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

`wasm/build.sh program` runs `pystachy ir`, adapts the IR to wasm32 (`wasm32_ir.py`),
compiles it with `clang --target=wasm32-wasi -O2` and links it with `wasm-ld` against the
runtime. The link treats a signature mismatch as an error, because a mismatched call traps.

## Without LLVM: the typed IR emitter

`tir_wasm.py` compiles a program's typed IR module, as `tools/typed_ir_text.py print` writes
it, straight to a WebAssembly module. That module does not link the runtime: it imports the
memory, functions and recursion state of `runtime.wasm`, the same runtime objects linked once
as a WASI reactor, and `run.mjs` instantiates both. The emitter is written in the subset, so
`wasm/build.sh emitter` compiles it to a native executable.

```sh
wasm/build.sh runtime-wasm               # build/wasm/runtime.wasm
wasm/build.sh emitter                    # build/wasm/tir_wasm (optional: else it runs on Python)
wasm/build.sh tir prog.py prog.wasm      # emitted, or through LLVM where the emitter refuses it
node --disable-warning=ExperimentalWarning wasm/run.mjs prog.wasm ARGS...
tests/run.sh ./pystachy wasm-tir tests/programs/apps/ouro2_*.py
```

Each typed IR value is a WebAssembly local, and so is a slot that only loads and stores
read. A function's blocks lie in order inside nested `block`s within a `loop`: a forward
branch is a `br` to its target's label, and a backward branch sets the next block's index
and continues the loop, whose `br_table` dispatches it. The emitter handles the operations
of scalar code, runtime calls, direct calls, globals, class fields, tuples and list items,
and constants (strings, tuples, field-name tables, class records), whose addresses
`run.mjs` relocates once it has allocated the program's data. It refuses, by name,
exception handlers, generators, function values (exception classes and callables among
constants), dynamic values, and classes that the runtime compares or prints through the
program's dispatchers; `wasm/build.sh tir` then builds the program through LLVM, and
`WASM_TIR_LOG` records which way each program went.

The typed IR module text comes from `tools/inspect_compiler.py` on Python, so `wasm/build.sh
tir` is not yet fast end to end: the compiler cannot print the module itself.

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
  rewritten as the address and a zero word (`wasm32_ir.py`). The compiler still reads some
  runtime records by 8-byte word index (a `DynType`'s class id and flags, class reflection
  records), so dynamic `Any` dispatch on classes and parts of reflection read the wrong field.

## Files

| File | Purpose |
|---|---|
| `build.sh` | Runtime, `runtime.wasm`, emitter and program builds |
| `run.mjs` | Node WASI runner, for a command or a module on `runtime.wasm` |
| `tir_wasm.py` | Typed IR module text to a WebAssembly module, without LLVM |
| `reactor.c` | `runtime.wasm`'s entry: arguments, `pys_init`, the program's code, `pys_finish` |
| `wasm32_ir.py` | IR rewrite for wasm32 constants, `main` and C library lengths |
| `wasi_stubs.c` | Missing POSIX functions, unwinder stubs, working directory |
| `include/` | Headers that `wasi-libc` lacks (`dlfcn.h`, `pthread.h`, `pwd.h`, `sys/wait.h`) and declarations `runtime.c` needs (`pystachy_wasi.h`) |
