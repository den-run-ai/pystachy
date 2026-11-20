"""wasm/tir_wasm.py: a typed IR module's text to a WebAssembly module, refusing by name what it
does not lower (wasm/README.md). Node validates the module where it is installed."""
import importlib.util
from pathlib import Path
import shutil
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

    def test_refusals_name_what(self):
        cases = {
            HELLO.replace("module complete", "module"): "complete",
            HELLO.replace("opts=[allocelide]", "opts=[allocelide] exceptions"): "exceptions",
            HELLO.replace("  ret\n", "  %t9 = gen.start : int\n  ret\n"): "operation gen.start",
            HELLO.replace("L6:\n", "L6: handler=L5\n"): "handler",
        }
        for text, what in cases.items():
            with self.assertRaises(T.Refused) as raised:
                emit(text)
            self.assertIn(what, raised.exception.what)


if __name__ == "__main__":
    unittest.main()
