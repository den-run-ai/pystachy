"""wasm/tir_wasm.py: a typed IR module's text to a WebAssembly module, refusing by name what it
does not lower (wasm/README.md). Node validates the module where it is installed."""
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("tir_wasm", ROOT / "wasm" / "tir_wasm.py")
T = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(T)

HELLO = """module complete opts=[allocelide] {
  const @s.0 kind=string text=" "
  const @s.1 kind=string text="\\n"
  const @s.2 kind=string text="hello, world"
  const @s.5 kind=string text="integer result does not fit in 64 bits"
  const @s.6 kind=string text=OverflowError
  runtime ovf.smul
  runtime write
  runtime str.int
  runtime raise
}

function @main.init() -> None effects="R A I rF wF" name=<module> kind=block {
entry:
  ~%t2 %t3 %t4 = ovf * (int 6, int 7) : int
  check message="OverflowError: integer result does not fit in 64 bits" (bool %t4) -> L6
L6:
  rt entry=write (str @s.2, int 1) : None
  rt entry=write (str @s.0, int 1) : None
  %t7 = rt entry=str.int (int %t3) : str
  rt entry=write (str %t7, int 1) : None
  rt entry=write (str @s.1, int 1) : None
  ret
"":
  br -> L5
L5:
  raise exception=OverflowError (str @s.6, str @s.5)
cold "OverflowError: integer result does not fit in 64 bits" -> L5
}
"""


EXCEPTION = """module complete {
  class E base=Exception fields=[] exception=Exception
  const @x.E kind=exception refs=[@s.2 @s.2 @show @show null]
  const @s.2 kind=string text=E
}
function @main.init() -> None kind=block {
entry:
  ret
}
function @show(self: E) -> str kind=class {
entry:
  ret (str @s.2)
}
"""

def emit(text):
    return bytes(T.Emitter(T.parse(text)).module())


class TirWasm(unittest.TestCase):
    def test_module(self):
        out = emit(HELLO)
        self.assertEqual(out[:8], b"\x00asm\x01\x00\x00\x00")
        for name in (b"pys_write", b"pys_str_int", b"pys_raise", b"pystachy.data", b"init"):
            self.assertIn(name, out)
        # the strings' Str headers: byte length, hash 0, characters + 1, then the bytes
        self.assertIn((12).to_bytes(8, "little") + bytes(8) + (13).to_bytes(8, "little") + b"hello, world\x00", out)

    @unittest.skipUnless(shutil.which("node"), "node validates the module")
    def test_node_validates(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "hello.wasm"
            path.write_bytes(emit(HELLO))
            check = "new WebAssembly.Module(require('fs').readFileSync(process.argv[1]))"
            subprocess.run(["node", "-e", check, str(path)], check=True)

    def test_constant_fields_and_float_slots(self):
        text = HELLO.replace('text="hello, world"', 'text=" items=(str @s.1)"')
        text = text.replace("  runtime ovf.smul", '  const @tc.0 kind=tuple items=(float "bitcast (i64 9218868437227405312 to double)", float "bitcast (i64 -4503599627370496 to double)")\n  runtime ovf.smul')
        module = T.Emitter(T.parse(text))
        module.lay_out_data()
        self.assertEqual(module.data[module.addr["@s.2"] + 24:][:17], b" items=(str @s.1)")
        self.assertEqual(module.data[module.addr["@tc.0"]:][:16], struct.pack("<dd", float("inf"), float("-inf")))

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_control_flow_and_packed_bool(self):
        # Each program records its result in its first (and only) global.
        preamble = """module complete {
  global @result type=int
}
function @main.init() -> None kind=block {
entry:
"""
        cases = [
            ("""  %t1 = slot.unpack (*bool 2) : bool
  cbr (bool %t1) -> yes, no
yes:
  mem.store (&int @result, int 1)
  ret
no:
  mem.store (&int @result, int 42)
  ret
""", False),
            ("""  %t0 = scalar.cast zext (%byte -1) : int
  %t1 = scalar.bin sub (int %t0, int 213) : int
  mem.store (&int @result, int %t1)
  ret
""", False),
            ("""  br -> next
next:
  %t0 = phi (int 0, int %t1) -> entry, next : int
  %t1 = scalar.bin add (int %t0, int 1) : int
  %t2 = num.cmp < (int %t1, int 42) : bool
  cbr (bool %t2) -> next, done
done:
  mem.store (&int @result, int %t1)
  ret
""", True),
        ]
        script = """
const fs = require('node:fs');
const mod = new WebAssembly.Module(fs.readFileSync(process.argv[1]));
const memory = new WebAssembly.Memory({ initial: 1 });
const instance = new WebAssembly.Instance(mod, { env: { memory, data: 0 }, rt: { pys_recursion_state: 0 } });
instance.exports.init();
console.log(new DataView(memory.buffer).getBigInt64(0, true).toString());
"""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "case.wasm"
            for body, has_backedge in cases:
                with self.subTest(has_backedge=has_backedge):
                    emitter = T.Emitter(T.parse(preamble + body + "}"))
                    path.write_bytes(emitter.module())
                    self.assertEqual(emitter.dispatch_local >= 0, has_backedge)
                    result = subprocess.check_output(["node", "-e", script, str(path)], text=True, timeout=10)
                    self.assertEqual(result.strip(), "42")

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_tuple_frames_share_and_restore_the_runtime_stack(self):
        program = """module complete {
}
function @main.init() -> None kind=block {
  %stk.1 = slot kind=2 : tuple[int,int,int]
  %stk.2 = slot kind=2 : tuple[int]
entry:
  rt entry=on_stack (%ptr %stk.1) : int
  rt entry=on_stack (%ptr %stk.2) : int
  call callee=@inner : None
  rt entry=on_stack (%ptr %stk.1) : int
  ret
}
function @inner() -> None {
  %stk.1 = slot kind=2 : tuple[int]
entry:
  rt entry=on_stack (%ptr %stk.1) : int
  ret.none
}
"""
        script = """
const assert = require('node:assert/strict');
const moduleBytes = require('node:fs').readFileSync(process.argv[1]);
const memory = new WebAssembly.Memory({initial: 1});
const sp = new WebAssembly.Global({value: 'i32', mutable: true}, 512);
const seen = [];
const instance = new WebAssembly.Instance(new WebAssembly.Module(moduleBytes), {
  env: {memory, data: 128},
  rt: {
    __stack_pointer: sp,
    pys_recursion_state: 0,
    pys_recursion_stack_error() { throw Error('stack floor'); },
    pys_on_stack(pointer) { seen.push([pointer, sp.value]); return 1n; },
  },
});
instance.exports.init();
assert.deepEqual(seen, [[480,480], [504,480], [464,464], [480,480]]);
assert.equal(sp.value, 512);
new DataView(memory.buffer).setBigInt64(16, 500n, true);
assert.throws(instance.exports.init, /stack floor/);
assert.equal(sp.value, 512);
assert.equal(seen.length, 4);
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frames.wasm"
            path.write_bytes(emit(program))
            subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)

    def test_frame_slot_refusals(self):
        program = """module complete {
}
function @main.init() -> None kind=block {
entry:
  ret
}
function @bad() -> tuple[int] {
  %stk.4 = slot kind=2 : tuple[int]
entry:
  ret (tuple[int] %stk.4)
}
"""
        with self.assertRaisesRegex(T.Refused, "return of frame slot %stk.4"):
            emit(program)
        for t in ("int", "vtuple[int]"):
            with self.subTest(t=t), self.assertRaisesRegex(T.Refused, "requires a fixed tuple"):
                emit(program.replace("slot kind=2 : tuple[int]", f"slot kind=2 : {t}"))

    @unittest.skipUnless(shutil.which("node"), "node runs the module")
    def test_invoke_restores_tuple_and_runtime_frames_before_handler(self):
        program = """module complete exceptions {
}
function @main.init() -> None kind=block {
  %stk.1 = slot kind=2 : tuple[int]
  %h.2 = slot : exc
entry:
  br -> body
body: handler=caught
  call callee=@inner -> done, caught : None
caught:
  ~%t3 ~%t4 = landing(%addr %h.2) -> handler : exc
handler:
  %t5 = mach.load(%ptr %h.2) : exc
  rt entry=on_stack (%ptr %t5) : int
  br -> done
done:
  rt entry=on_stack (%ptr %stk.1) : int
  ret
}
function @inner() -> None {
  %stk.1 = slot kind=2 : tuple[int]
entry:
  rt entry=on_stack (%ptr %stk.1) : int
  rt entry=list.get (list[int] null, int 0) : *int
  ret.none
}
"""
        script = """
const assert = require('node:assert/strict');
const mod = new WebAssembly.Module(require('node:fs').readFileSync(process.argv[1]));
const sp = new WebAssembly.Global({value: 'i32', mutable: true}, 512);
const tag = new WebAssembly.Tag({parameters: ['i32']});
const seen = [];
const instance = new WebAssembly.Instance(mod, {
  env: {memory: new WebAssembly.Memory({initial: 1}), data: 128, pystachy_exception: tag},
  rt: {
    __stack_pointer: sp,
    pys_recursion_state: 0,
    pys_recursion_stack_error() { throw Error('stack floor'); },
    pys_on_stack(pointer) { seen.push([pointer, sp.value]); return 1n; },
    pys_list_get() {
      sp.value -= 32; // Model a C frame whose epilogue is skipped by the exception.
      throw new WebAssembly.Exception(tag, [73]);
    },
  },
});
instance.exports.init();
assert.deepEqual(seen, [[480, 480], [73, 496], [496, 496]]);
assert.equal(sp.value, 512);
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unwind.wasm"
            legacy = emit(program)
            modern = bytes(T.Emitter(T.parse(program), True).module())
            self.assertNotEqual(legacy, modern)
            path.write_bytes(legacy)
            subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)
            # Independent feature probe: (module (func (try_table))).
            probe = "process.exit(WebAssembly.validate(Buffer.from('0061736d01000000010401600000030201000a080106001f40000b0b','hex')) ? 0 : 1)"
            if subprocess.run(["node", "-e", probe], check=False, timeout=10).returncode == 0:
                path.write_bytes(modern)
                subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)
        for before, after, reason in [
            ("-> done, caught", "-> done", "exception edges"),
            ("-> done, caught", "-> done, handler", "without a landing"),
            ("slot : exc", "slot : int", "exception slot"),
        ]:
            with self.subTest(after=after), self.assertRaisesRegex(T.Refused, reason):
                emit(program.replace(before, after))

    def test_exception_callback_signatures(self):
        self.assertIn(b"__indirect_function_table", emit(EXCEPTION))
        with self.assertRaisesRegex(T.Refused, "requires string names"):
            emit(EXCEPTION.replace("refs=[@s.2", "refs=[null"))
        for before, after in (("self: E", "self: int"), (" -> str kind", " -> int kind"),
                              ("@show @show null", "@show @missing null"),
                              ("@show @show null", "@show @show @show")):
            with self.subTest(after=after), self.assertRaisesRegex(T.Refused, "exception callback"):
                emit(EXCEPTION.replace(before, after))

    @unittest.skipUnless(shutil.which("node"), "node instantiates the module")
    def test_callbacks_append_to_the_reactor_table(self):
        script = """
const assert = require('node:assert/strict');
const mod = new WebAssembly.Module(require('node:fs').readFileSync(process.argv[1]));
const memory = new WebAssembly.Memory({initial: 1});
const words = new DataView(memory.buffer);
function load(data, table) {
  return new WebAssembly.Instance(mod, {env: {memory, data},
    rt: {pys_recursion_state: 0, __indirect_function_table: table}});
}
const table = new WebAssembly.Table({element: 'anyfunc', initial: 2});
const first = load(128, table);
table.set(1, first.exports.init);
load(256, table);
assert.equal(table.length, 4);
assert.equal(table.get(1), first.exports.init);
for (const [data, index] of [[128, 2], [256, 3]]) {
  assert.equal(words.getUint32(data + 8, true), index);
  assert.equal(words.getUint32(data + 12, true), index);
  assert.equal(words.getUint32(data + 16, true), 0);
  assert.equal(table.get(index)(0), data + 24); // @s.2 after the 20-byte descriptor and alignment padding
}
const fixed = new WebAssembly.Table({element: 'anyfunc', initial: 2, maximum: 2});
assert.throws(() => load(384, fixed), WebAssembly.RuntimeError);
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "callback.wasm"
            path.write_bytes(emit(EXCEPTION))
            subprocess.run(["node", "-e", script, str(path)], check=True, timeout=10)

    def test_refusals_name_what(self):
        cases = {
            HELLO.replace("entry=write", "entry=unknown"): "runtime entry unknown",
            HELLO.replace("module complete", "module"): "complete",
            HELLO.replace("opts=[allocelide]", "opts=[allocelide] dynamic"): "dynamic",
            HELLO.replace("  ret\n", "  %t9 = gen.start : int\n  ret\n"): "operation gen.start",
            HELLO.replace("  ret\n", "  %t9 = mach.addr element=dyntype (%ptr null, int 3) : %ptr\n  ret\n"): "mach.addr element dyntype",
            HELLO.replace("L6:\n", "L6: handler=L5\n"): "handler",
        }
        for text, what in cases.items():
            with self.assertRaises(T.Refused) as raised:
                emit(text)
            self.assertIn(what, raised.exception.what)

    def test_finalized_block_handler_syntax(self):
        program = HELLO.replace("module complete", "module complete exceptions")
        # A region can name a pad that finalization removed when it had no callers.
        self.assertEqual(emit(program), emit(program.replace("L6:", 'L6: handler="unused pad"')))
        for suffix in (" handler=", ' handler=""', ' handler="unterminated', " handler=pad extra", " handler=pad["):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(T.Refused, "handler"):
                T.parse(program.replace("L6:", "L6:" + suffix))


if __name__ == "__main__":
    unittest.main()
