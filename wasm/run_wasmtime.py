"""Run compiled Pystachy programs with the optional wasmtime Python package."""

import argparse
import io
import sys
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

import wasmtime as wt


DEFAULT_RUNTIME = Path(__file__).resolve().parents[1] / "build/wasm/runtime.wasm"
U32_MAX = (1 << 32) - 1
# wasmtime-py 51 stores a callback's pending Python exception in a process-global
# slot. A callback can reenter on the same thread or join another thread without
# deadlocking. Overlapping guest execution on separate threads fails immediately.
_guest_lock = RLock()


@contextmanager
def guest_execution():
    if not _guest_lock.acquire(blocking=False):
        raise RuntimeError("another thread is running Wasmtime; use a separate host process")
    try:
        yield
    finally:
        _guest_lock.release()

# Keep the exception inside Wasm, including when it crosses a C runtime frame.
# The table breaks the cycle between the reactor, guest, and bridge imports.
BRIDGE = """(module
  (type $void (func))
  (type $run (func (result i32)))
  (type $report (func (param i32)))
  (table (export "entry") 4 funcref)
  (tag $exc (export "exception") (param i32))
  (global $report_unwind (mut i32) (i32.const 0))
  (func (export "init")
    (call_indirect (type $void) (i32.const 1))  ;; pys_eh_on
    (call_indirect (type $void) (i32.const 0))) ;; guest.init
  (func (export "raise") (param $ptr i32)
    (if (global.get $report_unwind)
      (then (global.set $report_unwind (i32.const 0)))
      (else (throw $exc (local.get $ptr)))))
  (func (export "invoke") (param $report i32) (result i32 i32)
    (local $status i32)
    (block $caught (result i32)
      (try_table (catch $exc $caught)
        (if (local.get $report)
          (then
            ;; Pass the original unwind to C so it reports, then catch normally
            ;; when Python runs during reporting or in atexit callbacks.
            (global.set $report_unwind (i32.const 1))
            (call_indirect (type $report) (local.get $report) (i32.const 3))
            unreachable))
        (local.set $status (call_indirect (type $run) (i32.const 2))))
      (i32.const 0))
    (local.get $status)))"""


def u32(reader: io.BytesIO) -> int:
    value = 0
    for shift in range(0, 35, 7):
        byte = reader.read(1)
        if not byte or (shift == 28 and byte[0] > 15):
            break
        value |= (byte[0] & 127) << shift
        if byte[0] < 128:
            return value
    raise ValueError("invalid wasm32 integer in Pystachy custom section")


@dataclass(frozen=True)
class Program:
    module: wt.Module
    data_size: int | None
    relocs: tuple[int, ...]
    has_handlers: bool


def metadata(binary: bytes) -> tuple[int | None, tuple[int, ...], bool]:
    # Module() already validated the core binary. wasmtime-py 51 does not expose
    # custom sections. Read only our own section bodies, skipping code and data.
    stream = io.BytesIO(binary)
    stream.seek(8)
    sections = {}
    while kind := stream.read(1):
        end = u32(stream) + stream.tell()
        if kind == b"\0":
            name = stream.read(u32(stream))
            if name in {b"pystachy.data", b"pystachy.reloc", b"pystachy.eh"}:
                if name in sections:
                    raise ValueError(f"duplicate section {name!r}")
                sections[name] = io.BytesIO(stream.read(end - stream.tell()))
        stream.seek(end)
    if b"pystachy.data" not in sections:
        return None, (), False
    data_size = u32(sections[b"pystachy.data"])
    relocs = []
    if reloc := sections.get(b"pystachy.reloc"):
        for _ in range(u32(reloc)):
            offset = u32(reloc)
            if offset + 4 > data_size:
                raise ValueError("relocation outside Pystachy data")
            relocs.append(offset)
    return data_size, tuple(relocs), b"pystachy.eh" in sections


def install_tools(linker: wt.Linker, tools: Mapping[str, Callable[[str], str]]) -> None:
    pending = None
    i32 = wt.ValType.i32()

    def span(caller, pointer, length):
        memory = caller["memory"]
        start, length = pointer & U32_MAX, length & U32_MAX
        if start + length > memory.data_len(caller):
            raise wt.Trap("tool buffer outside guest memory")
        return memory, start, start + length

    def decode(caller, pointer, length):
        memory, start, end = span(caller, pointer, length)
        return memory.read(caller, start, end).decode("utf-8")

    def call(caller, name_ptr, name_len, payload_ptr, payload_len):
        nonlocal pending
        if pending is not None:
            raise wt.Trap("previous tool result has not been read")
        name = decode(caller, name_ptr, name_len)
        if name not in tools:
            raise wt.Trap(f"no host tool named {name}")
        value = tools[name](decode(caller, payload_ptr, payload_len))
        if not isinstance(value, str):
            raise TypeError(f"tool {name} must return a Unicode string synchronously")
        pending = value.encode("utf-8")
        if len(pending) > U32_MAX:
            raise OverflowError("tool reply exceeds wasm32")
        return len(pending)

    def read(caller, pointer, length):
        nonlocal pending
        if pending is None or length & U32_MAX != len(pending):
            raise wt.Trap("invalid tool result length")
        memory, start, _ = span(caller, pointer, length)
        if pending:
            memory.write(caller, pending, start)
        pending = None

    linker.define_func("codemode", "call", wt.FuncType([i32] * 4, [i32]), call, access_caller=True)
    linker.define_func("codemode", "read", wt.FuncType([i32] * 2, []), read, access_caller=True)


class Runner:
    def __init__(self, runtime: Path = DEFAULT_RUNTIME, *, max_wasm_stack: int | None = None):
        config = wt.Config()
        if max_wasm_stack is not None:
            # Engine creation requires 0 < max_wasm_stack <= async_stack_size.
            # wasmtime-py 51 leaves async_stack_size at Wasmtime's 2 MiB default.
            if type(max_wasm_stack) is not int or not 0 < max_wasm_stack <= 2 * 1024 * 1024:
                raise ValueError("max_wasm_stack must be an integer from 1 to 2097152 bytes")
            config.max_wasm_stack = max_wasm_stack
        config.wasm_exceptions = True
        config.consume_fuel = True
        self.engine = wt.Engine(config)
        self.runtime_path = runtime
        self.runtime = None
        self.dispatchers = []
        self.catchable_runtime = False
        self.bridge = None

    def compile(self, binary: bytes) -> Program:
        if binary[:4] != b"\0asm":
            raise ValueError("expected a compiled Wasm binary")
        module = wt.Module(self.engine, binary)
        return Program(module, *metadata(binary))

    def run(self, program: Program, *, tools: Mapping[str, Callable[[str], str]] | None = None,
            args: Sequence[str] = ("program",), env: Mapping[str, str] | None = None,
            fuel: int = (1 << 64) - 1, memory_limit: int | None = None,
            stdout: Path | None = None, stderr: Path | None = None, inherit_stdin: bool = False) -> int:
        if not 0 <= fuel < 1 << 64:
            raise ValueError("fuel must fit an unsigned 64-bit integer")
        if memory_limit is not None and not 0 <= memory_limit < 1 << 63:
            raise ValueError("memory_limit must fit a nonnegative signed 64-bit integer")
        with guest_execution(), wt.Store(self.engine) as store, wt.Linker(self.engine) as linker:
            store.set_fuel(fuel)
            if memory_limit is not None:
                store.set_limits(memory_size=memory_limit)
            wasi = wt.WasiConfig()
            wasi.argv = list(args)
            wasi.env = (env or {}).items()
            if inherit_stdin:
                wasi.inherit_stdin()
            if stdout is None:
                wasi.inherit_stdout()
            else:
                wasi.stdout_file = str(stdout)
            if stderr is None:
                wasi.inherit_stderr()
            else:
                wasi.stderr_file = str(stderr)
            store.set_wasi(wasi)
            linker.define_wasi()
            # Wasmtime's Preview 1 proc_exit rejects codes >= 126. Match the
            # reactor/command ABI for SystemExit, including negative Python codes.
            class GuestExit(Exception):
                pass

            def proc_exit(code):
                raise GuestExit(code & U32_MAX)

            linker.allow_shadowing = True
            linker.define_func("wasi_snapshot_preview1", "proc_exit", wt.FuncType([wt.ValType.i32()], []), proc_exit)
            linker.allow_shadowing = False
            install_tools(linker, tools or {})
            # runtime.c's tracebacks ask the host for the engine's stack, which wasmtime-py does not
            # give a host function: an uncaught error shows its last line alone
            i32 = wt.ValType.i32()
            linker.define_func("pystachy", "trace", wt.FuncType([], []), lambda: None)
            linker.define_func("pystachy", "frames", wt.FuncType([i32] * 3, [i32]), lambda *_: 0)
            linker.define_func("pystachy", "lines", wt.FuncType([i32] * 2, [i32]), lambda *_: 0)
            try:
                if program.data_size is None:
                    command = linker.instantiate(store, program.module)
                    command.exports(store)["_start"](store)
                    return 0
                return self._run_direct(store, linker, program)
            except GuestExit as exit_status:
                return exit_status.args[0]

    def _run_direct(self, store, linker, program):
        if self.runtime is None:
            self.runtime = wt.Module.from_file(self.engine, self.runtime_path)
            imports = self.runtime.imports
            self.catchable_runtime = any(imp.module == "program" and imp.name == "raise"
                                         and isinstance(imp.type, wt.FuncType) for imp in imports)
            self.dispatchers = [(imp.name, imp.type) for imp in imports if imp.module == "env"
                                and imp.name in {"pys_obj_eq", "pys_obj_cmp", "pys_obj_repr"}]
        bridge = None
        if program.has_handlers:
            if not self.catchable_runtime:
                raise ValueError("this program requires a runtime with catchable exceptions; rebuild runtime-wasm")
            if self.bridge is None:
                self.bridge = wt.Module(self.engine, BRIDGE)
            bridge = wt.Instance(store, self.bridge, []).exports(store)
            linker.define(store, "env", "pystachy_exception", bridge["exception"])
            linker.define(store, "program", "raise", bridge["raise"])
            linker.define(store, "program", "init", bridge["init"])
        else:
            linker.define_func("program", "raise", wt.FuncType([wt.ValType.i32()], []), lambda _: None)
            linker.define_func("program", "init", wt.FuncType([], []),
                               lambda caller: guest.exports(caller)["init"](caller), access_caller=True)

        for name, typ in self.dispatchers:
            def missing(*_, name=name):
                raise wt.Trap(f"{name}: the program has no such dispatcher")
            linker.define_func("env", name, typ, missing)
        reactor = linker.instantiate(store, self.runtime)
        linker.define_instance(store, "rt", reactor)

        # Instance.exports() materializes thousands of C runtime exports in Python.
        # Resolve just the names the host actually calls.
        def export(name):
            return linker.get(store, "rt", name)

        export("_initialize")(store)
        data = export("malloc")(store, max(8, program.data_size)) & U32_MAX
        if not data:
            raise MemoryError("no room for the program's data")
        memory = export("memory")
        linker.define(store, "env", "memory", memory)
        linker.define(store, "env", "data", wt.Global(store, wt.GlobalType(wt.ValType.i32(), False), data))
        guest = linker.instantiate(store, program.module)
        for offset in program.relocs:
            at = data + offset
            relative = int.from_bytes(memory.read(store, at, at + 4), "little")
            memory.write(store, ((relative + data) & U32_MAX).to_bytes(4, "little"), at)
        if bridge is None:
            return export("pys_wasi_run")(store)
        functions = (guest.exports(store)["init"], export("pys_eh_on"), export("pys_wasi_run"), export("pys_throw"))
        for index, function in enumerate(functions):
            bridge["entry"].set(store, index, function)
        stack = export("__stack_pointer")
        saved = stack.value(store)
        uncaught = 0
        while True:
            uncaught, status = bridge["invoke"](store, uncaught)
            if not uncaught:
                return status
            stack.set_value(store, saved)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("program", type=Path)
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    runner = Runner(options.runtime)
    try:
        status = runner.run(runner.compile(options.program.read_bytes()),
                            args=[str(options.program), *options.args], inherit_stdin=True)
        return status & 255
    except wt.Trap as exc:
        print(f"wasm trap: {exc}", file=sys.stderr)
        return 134
    except (wt.WasmtimeError, ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
