"""Host contracts, without a native frontend or WASI SDK."""

import tempfile
import unittest
from pathlib import Path
from threading import Thread

import wasmtime as wt

from wasm.run_wasmtime import Runner


# Return the word at the start of the allocated program data as the guest's status.
REACTOR = """(module
  (import "program" "init" (func $init))
  (import "program" "raise" (func $raise (param i32)))
  (memory (export "memory") 1)
  (global $sp (export "__stack_pointer") (mut i32) (i32.const 96))
  (func (export "_initialize"))
  (func (export "malloc") (param i32) (result i32) i32.const 32)
  (func (export "pys_wasi_run") (result i32) call $init i32.const 32 i32.load)
  (func (export "pys_eh_on"))
  (func (export "pys_throw") (param i32)
    ;; An uncaught Python exception must return here with the C stack restored.
    (if (i32.ne (global.get $sp) (i32.const 96)) (then unreachable))
    (i32.store (i32.const 32) (local.get 0))
    (call $raise (local.get 0)))
  (func (export "fail") (global.set $sp (i32.const 8)) (call $raise (i32.const 17))))"""


class HostTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        runtime = Path(directory.name) / "runtime.wasm"
        runtime.write_bytes(wt.wat2wasm(REACTOR))
        self.runner = Runner(runtime)

    def compile(self, wat):
        return self.runner.compile(wt.wat2wasm(wat))

    def test_relocations(self):
        program = self.compile(r'''(module
          (@custom "pystachy.data" "\08") (@custom "pystachy.reloc" "\01\00")
          (import "env" "memory" (memory 1)) (import "env" "data" (global $base i32))
          (data (global.get $base) "\04\00\00\00") (func (export "init")))''')
        self.assertEqual(self.runner.run(program), 36)
        self.assertEqual(self.runner.run(program), 36)
        with self.assertRaisesRegex(ValueError, "relocation outside"):
            self.compile(r'(module (@custom "pystachy.data" "\08") (@custom "pystachy.reloc" "\01\05"))')
        with self.assertRaisesRegex(ValueError, "wasm32 integer"):
            self.compile(r'(module (@custom "pystachy.data" "\80"))')

    def test_caught_and_uncaught(self):
        fields = r'''(@custom "pystachy.data" "\08") (@custom "pystachy.eh" "")
          (import "env" "pystachy_exception" (tag $exc (param i32)))
          (import "rt" "fail" (func $fail)) (import "env" "memory" (memory 1))'''
        caught = self.compile(f'''(module {fields} (func (export "init")
          i32.const 32 (block $handler (result i32)
            (try_table (catch $exc $handler) call $fail) unreachable)
          i32.const 1 i32.add i32.store))''')
        uncaught = self.compile(f'(module {fields} (func (export "init") call $fail))')
        self.assertEqual(self.runner.run(caught), 18)
        self.assertEqual(self.runner.run(uncaught), 17)

    def test_tools_are_per_call(self):
        program = self.compile(r'''(module
          (import "codemode" "call" (func $call (param i32 i32 i32 i32) (result i32)))
          (import "codemode" "read" (func $read (param i32 i32)))
          (import "wasi_snapshot_preview1" "proc_exit" (func $exit (param i32)))
          (memory (export "memory") 1) (data (i32.const 0) "lookupλ")
          (func (export "_start") (call $read (i32.const 16)
            (call $call (i32.const 0) (i32.const 6) (i32.const 6) (i32.const 2)))
            (call $exit (i32.load8_u (i32.const 16)))))''')
        for reply in ["", "A", "B"]:
            seen = []

            def lookup(value, reply=reply, seen=seen):
                seen.append(value)
                return reply

            self.assertEqual(self.runner.run(program, tools={"lookup": lookup}), ord(reply) if reply else 0)
            self.assertEqual(seen, ["λ"])
        with self.assertRaisesRegex(wt.Trap, "no host tool named lookup"):
            self.runner.run(program)
        with self.assertRaisesRegex(TypeError, "Unicode string"):
            self.runner.run(program, tools={"lookup": lambda _: 42})

    def test_out_of_bounds_payload_does_not_reach_callback(self):
        program = self.compile('''(module
          (import "codemode" "call" (func $call (param i32 i32 i32 i32) (result i32)))
          (memory (export "memory") 1) (data (i32.const 0) "t")
          (func (export "_start") (drop (call $call (i32.const 0) (i32.const 1)
            (i32.const 65535) (i32.const 2)))))''')
        with self.assertRaisesRegex(wt.Trap, "outside guest memory"):
            self.runner.run(program, tools={"t": self.fail})

    def test_older_runtime_rejects_handlers(self):
        self.runner.runtime_path.write_bytes(wt.wat2wasm('(module)'))
        program = self.compile(r'(module (@custom "pystachy.data" "\08") (@custom "pystachy.eh" ""))')
        with self.assertRaisesRegex(ValueError, "requires a runtime with catchable exceptions"):
            self.runner.run(program)

    def test_linear_memory_limit_is_per_call(self):
        program = self.compile('''(module (memory 1)
          (func (export "_start") (if (i32.eq (memory.grow (i32.const 1)) (i32.const -1))
            (then unreachable))))''')
        with self.assertRaises(wt.WasmtimeError):
            self.runner.run(program, memory_limit=65535)
        with self.assertRaises(wt.Trap):
            self.runner.run(program, memory_limit=65536)
        self.assertEqual(self.runner.run(program, memory_limit=131072), 0)

    def test_callback_can_reenter_and_detects_an_overlapping_thread(self):
        outer = self.compile('''(module
          (import "codemode" "call" (func $call (param i32 i32 i32 i32) (result i32)))
          (memory (export "memory") 1) (data (i32.const 0) "tool")
          (func (export "_start") (drop (call $call (i32.const 0) (i32.const 4)
            (i32.const 0) (i32.const 0)))))''')
        other = Runner()
        inner = other.compile(wt.wat2wasm('(module (func (export "_start")))'))
        results = []

        def parallel():
            try:
                results.append(other.run(inner))
            except RuntimeError as exc:
                results.append(str(exc))

        def tool(_):
            results.append(other.run(inner))
            thread = Thread(target=parallel, daemon=True)
            thread.start()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            return ""

        self.assertEqual(self.runner.run(outer, tools={"tool": tool}), 0)
        self.assertEqual(results[0], 0)
        self.assertIn("another thread", results[1])
        self.assertEqual(other.run(inner), 0)

    def test_full_wasi_exit_codes(self):
        for code in [0, 125, 126, 255, 293, -1]:
            program = self.compile(f'''(module
              (import "wasi_snapshot_preview1" "proc_exit" (func $exit (param i32)))
              (func (export "_start") (call $exit (i32.const {code}))))''')
            self.assertEqual(self.runner.run(program), code & 0xFFFFFFFF)

    def test_fuel_is_per_call(self):
        program = self.compile('(module (func (export "_start") (loop $l br $l)))')
        for fuel in [0, 1000]:
            with self.assertRaises(wt.Trap) as raised:
                self.runner.run(program, fuel=fuel)
            self.assertEqual(raised.exception.trap_code, wt.TrapCode.OUT_OF_FUEL)


if __name__ == "__main__":
    unittest.main()
