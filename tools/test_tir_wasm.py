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

    def test_refusals_name_what(self):
        cases = {
            HELLO.replace("entry=write", "entry=unknown"): "runtime entry unknown",
            HELLO.replace("module complete", "module"): "complete",
            HELLO.replace("opts=[allocelide]", "opts=[allocelide] exceptions"): "exceptions",
            HELLO.replace("  ret\n", "  %t9 = gen.start : int\n  ret\n"): "operation gen.start",
            HELLO.replace("  ret\n", "  %t9 = mach.addr element=dyntype (%ptr null, int 3) : %ptr\n  ret\n"): "mach.addr element dyntype",
            HELLO.replace("L6:\n", "L6: handler=L5\n"): "handler",
        }
        for text, what in cases.items():
            with self.assertRaises(T.Refused) as raised:
                emit(text)
            self.assertIn(what, raised.exception.what)


if __name__ == "__main__":
    unittest.main()
