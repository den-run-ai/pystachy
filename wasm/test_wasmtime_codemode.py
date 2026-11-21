"""End-to-end Wasmtime host tests using the built native emitter and WASI runtime."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from wasm.run_wasmtime import Runner


class CodeModeTests(unittest.TestCase):
    def test_tool_reply_on_both_routes(self):
        header = 'from codemode import call\n'
        sources = {
            "direct": header + '''try:
    print(int(call("lookup", "λ")))
except ValueError:
    print("caught ValueError")
''',
            "program": header + 'print(call("lookup", "λ"))\n',
        }
        runner = Runner(Path(os.environ.get("WASM_RUNTIME", "build/wasm")) / "runtime.wasm")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, binary, out, err = [root / name for name in ("tool.py", "tool.wasm", "out", "err")]
            for route, text in sources.items():
                with self.subTest(route=route):
                    source.write_text(text, encoding="utf-8")
                    subprocess.run(["wasm/build.sh", route, source, binary], check=True,
                                   env={**os.environ, "WASM_EH": "standard"})
                    program = runner.compile(binary.read_bytes())
                    self.assertEqual(program.data_size is not None, route == "direct")
                    self.assertEqual(program.has_handlers, route == "direct")
                    calls = []

                    def lookup(payload, calls=calls):
                        calls.append(payload)
                        return "résultat"

                    self.assertEqual(runner.run(program, stdout=out, stderr=err, tools={"lookup": lookup}), 0)
                    self.assertEqual(calls, ["λ"])
                    self.assertEqual(out.read_text(), "caught ValueError\n" if route == "direct" else "résultat\n")
                    self.assertEqual(err.read_bytes(), b"")
