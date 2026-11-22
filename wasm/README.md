# WebAssembly (experimental)

This directory builds Pystachy programs for `wasm32-wasi` (WASI preview 1) and runs them
under Node or Wasmtime. Short typed programs can reach WebAssembly directly from finalized typed IR or
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
read. In a recursion-counted function, values of one type whose lifetimes do not overlap
share a local. Fixed-size tuple temporaries use the reactor's 16-byte-aligned stack. A
callee can recognize and copy a `*args` tuple before it escapes its caller.
Modules with tuple frames or exception landing pads import the stack pointer.

A function's blocks lie in order inside nested `block`s. A forward branch is a `br` to its
target's label, or falls through to the next block. A function with a backward branch also
has a `loop` around them: that branch sets the next block's index and continues the loop,
whose `br_table` dispatches it. The emitter handles the operations
of scalar code, runtime calls, direct calls, globals, class fields, tuples and list items,
and constants (strings, tuples, field-name tables, class records), whose addresses
`run.mjs` relocates once it has allocated the program's data. Masked integer expressions such
as `(x * 33 + y) & 0xffffffff` use Wasm `i32` arithmetic when the compiler has reduced them
to 32 bits. The final widening preserves the unsigned result.

Python handlers can catch built-in and user-defined exceptions raised locally, by other
Python functions, or by the shared runtime. An exception class descriptor holds the indices
of its string, representation and optional exit callbacks in the reactor's function table.
When instantiating a module with descriptors, its Wasm start function appends these
callbacks after the runtime's entries. Rebuild older reactors with `wasm/build.sh runtime-wasm`
to enable table growth. For a call with an unwind edge, a typed Wasm catch restores the
reactor's stack pointer and branches to the landing pad in the finalized IR. The runtime
performs exception matching, cleanup and uncaught reporting, including `SystemExit`.
Each run has its own Python exception tag. Host tool failures and Wasm traps still end
the Node run with status 134. The direct exception fixtures in `wasm/test_codemode.mjs` have
been verified on Node 22.23.0 and 24.22.3.

Set `WASM_EH=standard` to emit standard `try_table` handlers for engines such as
Wasmtime (enable its exceptions proposal). Both the source and module-text frontends
emit these instructions directly. When LLVM 18/19 produces a WASI command with
exception handlers, the build runs Binaryen's `wasm-opt --emit-exnref` after linking
(tested with Binaryen 132). Commands without handlers need no conversion.
The default, `WASM_EH=legacy`, also supports early Node 22 releases whose engines
reject `try_table`. Both encodings use the same runtime and Python exception tag.

The direct emitter gives a named refusal for generators, function values, dynamic values
and classes that need
runtime comparison or printing through the program's dispatchers. `wasm/build.sh tir`
then builds the program through LLVM, and `WASM_TIR_LOG` records the route taken.

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
process. The Node host has no fuel accounting or suspend/resume API.

Run `node --no-warnings bench/startup/wasm.mjs 11` from the checkout to measure
source compilation, a fresh guest in a warm host, and source-to-exit latency in warm
and fresh Node processes. It checks a distinct snippet for every sample, covering hello,
a directly emitted tool-result filter, and two filters for the same JSON records.
The [typed filter](../bench/startup/wasm_json_filter.py) uses `json.loads` and narrows its
recursive `JSONValue` with `isinstance`; it runs directly. The original `json` benchmark
uses the dynamic `Any` decoder and takes the LLVM fallback. The typed decoder has the
[same integer and nesting limits](../docs/json.md) as on the native backend.

## Calling tools from a Wasmtime host

Install `wasmtime==51.0.0` in the Python environment running the host. Build a program with
`WASM_EH=standard wasm/build.sh tir prog.py prog.wasm` so that any exception handlers use
standard `try_table` encoding. `python wasm/run_wasmtime.py prog.wasm ARGS...` runs the
result. Use `--runtime PATH` before the program name for a different reactor. Standalone
LLVM/WASI commands need only the program file.

```python
from pathlib import Path
from wasm.run_wasmtime import Runner

runner = Runner()
program = runner.compile(Path("prog.wasm").read_bytes())
status = runner.run(program, tools={"issues": lambda project: "closed\nopen\nopen"},
                    fuel=1_000_000, memory_limit=64 * 1024 * 1024)
```

Reuse the runner and compiled program across calls. Each call creates a fresh store with
its own tool grants, empty stdin, arguments (including argv[0]) and environment (empty by
default). Both interfaces inherit stdout and stderr and grant no directory mounts. The
Python API also accepts `stdout` and `stderr` file paths, truncating each file on each run.
`run` returns the unsigned 32-bit WASI exit status. The CLI exposes its low eight bits. Wasmtime traps and host callback errors propagate to
the Python caller. The CLI prints a trap diagnostic and exits with status 134. Calls to
this runner from overlapping threads raise `RuntimeError` because wasmtime-py 51 shares
its pending callback exception across threads. A callback may run another guest on the
same thread. Use separate processes for parallel execution.

`fuel` bounds Wasm execution in engine-defined units. It excludes host callback time and
compilation. `memory_limit` caps each guest linear memory in bytes. A cap below the initial
memory size fails instantiation, and growth beyond the cap returns the Wasm `memory.grow`
failure value. The limit excludes engine code, tables and host allocations.

`Runner(max_wasm_stack=2 * 1024 * 1024)` configures the engine's native stack budget
for guest execution. The default is Wasmtime 51's 512 KiB. Deep recursive programs
can hit a Wasmtime stack-overflow trap before reaching Python's `RecursionError`.
Only raise the budget when every calling thread has that much native stack available
on entry, plus headroom for host callbacks, Python frames and the engine. The runner
never resizes the OS thread stack. The pinned Python binding supports up to 2 MiB.
On Linux x86-64, the directly emitted `json_depth` fixture matched its Python recording
at 1 MiB and 2 MiB with over 7 MiB of native stack available on entry. The fixture
covers a 2,000-container round trip and catching `RecursionError` on deeper inputs.

## What differs from a native build

- **The collector is off.** The conservative stack scan cannot see WebAssembly locals, so
  `runtime.c` sets `PYSTACHY_GC=off` under WASI. The engine caps memory (4 GiB for wasm32).
- **LLVM/WASI commands use WebAssembly exception handling.** The adapter lowers native
  landing pads to Wasm catches for Pystachy's exception payload. A catch unwinds to the
  handler of the enclosing `try`, as clang's nested catches do: LLVM counts the handler's
  code as part of its catch. Python handlers, cleanup and uncaught reporting use the shared
  runtime. WASI errno numbers can differ from Linux,
  including which subclass a numeric `OSError` constructs. For example, both Wasm routes
  report missing files with WASI errno 44, while Linux reports errno 2.
- **No processes, signals, users or dynamic loading.** `wasi_stubs.c` defines those calls to
  fail with `ENOSYS`, so the runtime raises the matching `OSError`.
- **Filesystem access depends on the runner.** The CLI preopens `/` and passes Node's working
  directory as `PWD`. The embedded code mode host supplies no directory mounts.
- **The C library's stdio is musl's.** Its `fwrite` of zero bytes still switches a stream that
  was reading to writing. That drops the read-ahead without moving the descriptor back, and
  marks a read-only stream failed. The runtime skips such writes, which glibc ignores.
- **Pointers are 4 bytes.** Compiled code addresses the runtime's structs through their LLVM
  types, which follow the target's layout. Constants that hold an address in a 64-bit slot are
  rewritten as the address and a zero word (`wasm32_ir.py`). Dynamic class dispatch and
  reflection read the name, class id and flags at their target-specific offsets in `DynType`
  and the flags in a class reflection record.
  A boxed class record pointer occupies an eight-byte payload slot on both targets.
  `vars()` reads an object's reference fields at the target's pointer width beside its 8-byte
  ints and floats. A frame keeps its locals above its frame address on wasm32, `@main`'s too,
  so the runtime finds a `*args` tuple that a caller made anywhere on the linear-memory stack
  above the callee and copies it before the callee keeps it.
- **The math library is musl's.** Some results differ from glibc's in the last place: musl's
  `cbrt(27)` is exactly 3.0. Two musl results would also be wrong for Python, so the runtime
  corrects them: `float("-nan")` keeps its sign, and `math.fma` keeps the sign of a product
  that rounds to zero when the addend is zero (`wasi_stubs.c`).

## Checking the whole corpus

`known_differences.txt` lists each corpus program whose output in the Wasm modes differs
from CPython's recording, with its reason: one of the differences above, or the pull request
that fixes it. `check_corpus.py` runs `tests/run.sh` in both modes and fails on any other
difference, so a new one is a regression or needs a reason. It names entries that now match;
remove them once their fix lands. The whole corpus takes about half an hour on four cores.

```sh
python3 wasm/check_corpus.py                       # every program, both modes
python3 wasm/check_corpus.py --modes wasm tests/programs/io/*.py
python3 wasm/check_corpus.py --log report.txt      # a tests/run.sh report of the same run
```

## Files

| File | Purpose |
|---|---|
| `build.sh` | Runtime, `runtime.wasm`, emitter and program builds |
| `check_corpus.py`, `known_differences.txt` | The corpus in the Wasm modes against its known, explained differences |
| `run.mjs`, `run_wasmtime.py` | Node and Python/Wasmtime runners for commands and direct modules |
| `codemode.mjs`, `tools.mjs` | String-source host and synchronous tool imports |
| `../tools/wasm_from_source.py` | Source to Wasm from finalized compiler records |
| `tir_wasm.py` | Typed IR module text to a WebAssembly module, without LLVM |
| `reactor.c` | `runtime.wasm`'s entry: arguments, `pys_init`, the program's code, `pys_finish` |
| `wasm32_ir.py` | Adapts constants, command entry, exception landing pads and libc calls to wasm32 |
| `command_eh.c` | Transfers exception payloads to LLVM/WASI command handlers and resumes uncaught reporting |
| `wasi_stubs.c` | Missing POSIX functions, unwinder stubs, working directory |
| `include/` | Headers that `wasi-libc` lacks (`dlfcn.h`, `pthread.h`, `pwd.h`, `sys/wait.h`) and declarations `runtime.c` needs (`pystachy_wasi.h`) |
