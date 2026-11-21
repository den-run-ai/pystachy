# WebAssembly (experimental)

This directory builds Pystachy programs for `wasm32-wasi` (WASI preview 1) and runs them
under Node. Short typed programs can reach WebAssembly directly from finalized typed IR or
through LLVM. Both routes use the same runtime (`runtime.c` and `runtime.py`).

## Build and run

The toolchain is the LLVM 18 that the native build uses, plus Ubuntu's `lld-18`, `wasi-libc` and
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
under load, about ten programs per corpus run. The runner wraps each WASI import in a
JavaScript function. This avoids the affected fast-call path within the guest and leaves
the embedding process's V8 flags alone.

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
wasm/build.sh emitter                    # native source and module-text compilers
wasm/build.sh direct prog.py prog.wasm   # direct only, exit 3 on an unsupported operation
wasm/build.sh tir prog.py prog.wasm      # emitted, or through LLVM where the emitter refuses it
node --disable-warning=ExperimentalWarning wasm/run.mjs prog.wasm ARGS...
tests/run.sh ./pystachy wasm-tir tests/programs/apps/ouro2_*.py
```

Each typed IR value is a WebAssembly local, and so is a slot that only loads and stores
read. Fixed-size tuple temporaries use the reactor's 16-byte-aligned stack. A
callee can recognize and copy a `*args` tuple before it escapes its caller.
Only modules with tuple frames import the stack pointer.

A function's blocks lie in order inside nested `block`s within a `loop`. A forward
branch is a `br` to its target's label, and a backward branch sets the next block's index
and continues the loop, whose `br_table` dispatches it. The emitter handles the operations
of scalar code, runtime calls, direct calls, globals, class fields, tuples and list items,
and constants (strings, tuples, field-name tables, class records), whose addresses
`run.mjs` relocates once it has allocated the program's data. It refuses, by name,
exception handlers, generators, function values (exception classes and callables among
constants), dynamic values, and classes that the runtime compares or prints through the
program's dispatchers; `wasm/build.sh tir` then builds the program through LLVM, and
`WASM_TIR_LOG` records which way each program went.

The source compiler passes the finalized functions and declarations directly to the emitter.
`build/wasm/wasm_from_source SOURCE.py OUT.wasm` compiles a file in one process. Use `- -`
for UTF-8 source on stdin and binary Wasm on stdout. For existing module text, use
`build/wasm/tir_wasm MODULE.tir OUT.wasm`. The shell build can also run the source compiler
on Python when the native executable is absent. In fallback mode a named refusal reuses
the same compilation's LLVM IR. Input errors and failed builds propagate to the caller.

## Calling tools from a Node host

Build the runtime and emitters once with the commands above. A host can then keep its
compiled runtime module across snippets. Each snippet gets fresh memory, globals and WASI
state. This example prints `open 2`.

```js
import { createCodeMode } from "./wasm/codemode.mjs";

const runPython = createCodeMode();
const tools = new Map([["issues", project => "closed\nopen\nopen"]]);
const status = await runPython(`
from codemode import call
states = call("issues", "pystachy").split("\\n")
print("open", states.count("open"))
`, { tools });
```

`codemode.call(name, payload) -> str` invokes one synchronous JavaScript callback.
Names, payloads and replies are Unicode strings. An unregistered name, callback exception
or invalid reply traps the guest (status 134). Compilation errors reject the promise.
An unsupported snippet takes the LLVM path using the same finalized IR and the checkout's
prebuilt runtime objects. The streaming fallback uses clang at `-O0` to reduce compile
latency on short scripts. Set `WASM_OPT=2` for longer-running computations. Hosts can set `fallback: false` to require direct compilation
and receive the named refusal as error code 3. That configuration needs no LLVM at run time.

`createCodeMode({compiler, runtime, cwd, fallback})` accepts alternate artifact paths and a source
import directory. `createRunner(runtime)` in `run.mjs` accepts already compiled program
bytes, a file path or a `WebAssembly.Module`. Both hosts accept per-call `args` (including
argv[0]), `env`, `tools` and numeric `stdin`, `stdout`, `stderr` descriptors. Embedded
runs start with an empty environment and no directory mounts. Stdio defaults to the host
descriptors. The command-line runner exposes the host filesystem and environment.

For repeated source, compile once and pass the returned module to a runner. The
compiler reports `backend` (`"direct"` or `"llvm"`) and `refusal` (the direct
emitter's diagnostic on fallback, otherwise `null`). The caller controls the
module's lifetime. Each execution supplies its own tools and starts with fresh
guest state.

```js
import { createCompiler } from "./wasm/codemode.mjs";
import { createRunner } from "./wasm/run.mjs";

const compile = createCompiler();
const run = createRunner();
const { module } = await compile('from codemode import call\nprint(call("lookup", "id"))');
await run(module, { tools: new Map([["lookup", id => "first"]]) });
await run(module, { tools: new Map([["lookup", id => "second"]]) });
```

Guest execution and callbacks are synchronous on the Node thread. Both runner
APIs accept an optional positive integer `executionTimeoutMs` per call. Expiry
during instantiation or execution rejects the promise with
`ERR_SCRIPT_EXECUTION_TIMEOUT`. Source compilation, linking and module
compilation occur before the timer starts. A blocking native host call can
delay interruption, and a tool may already have performed external work.
A hard deadline over the complete request requires a separately supervised
process. Fuel accounting and suspend/resume remain open.

Run `node --no-warnings bench/startup/wasm.mjs 11` from the checkout to measure
source compilation, a fresh guest in a warm host, and source-to-exit latency in warm
and fresh Node processes. It checks a distinct snippet for every sample, covering hello,
a directly emitted tool-result filter, and a JSON filter using dynamic `Any` and the LLVM fallback.

## What differs from a native build

- **The collector is off.** The conservative stack scan cannot see WebAssembly locals, so
  `runtime.c` sets `PYSTACHY_GC=off` under WASI. The engine caps memory (4 GiB for wasm32).
- **A raise ends the program.** `llc` lowers each `invoke` to a call, and the unwinder stubs
  (`wasi_stubs.c`) never find a handler. An uncaught exception prints CPython's last line and
  exit status, but `try`, `with` and `except` cannot catch anything.
- **No processes, signals, users or dynamic loading.** `wasi_stubs.c` defines those calls to
  fail with `ENOSYS`, so the runtime raises the matching `OSError`.
- **Filesystem access depends on the runner.** The CLI preopens `/` and passes Node's working
  directory as `PWD`. The embedded code mode host supplies no directory mounts.
- **Pointers are 4 bytes.** Compiled code addresses the runtime's structs through their LLVM
  types, which follow the target's layout. Constants that hold an address in a 64-bit slot are
  rewritten as the address and a zero word (`wasm32_ir.py`). Dynamic class dispatch and
  reflection read the name, class id and flags at their target-specific offsets in `DynType`
  and the flags in a class reflection record.
  A boxed class record pointer occupies an eight-byte payload slot on both targets.

## Files

| File | Purpose |
|---|---|
| `build.sh` | Runtime, `runtime.wasm`, emitter and program builds |
| `run.mjs` | Node WASI runner, for a command or a module on `runtime.wasm` |
| `codemode.mjs`, `tools.mjs` | String-source host and synchronous tool imports |
| `../tools/wasm_from_source.py` | Source to Wasm from finalized compiler records |
| `tir_wasm.py` | Typed IR module text to a WebAssembly module, without LLVM |
| `reactor.c` | `runtime.wasm`'s entry: arguments, `pys_init`, the program's code, `pys_finish` |
| `wasm32_ir.py` | IR rewrite for wasm32 constants, `main` and C library lengths |
| `wasi_stubs.c` | Missing POSIX functions, unwinder stubs, working directory |
| `include/` | Headers that `wasi-libc` lacks (`dlfcn.h`, `pthread.h`, `pwd.h`, `sys/wait.h`) and declarations `runtime.c` needs (`pystachy_wasi.h`) |
