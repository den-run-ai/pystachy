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

    def test_direct_recordings(self):
        runner = Runner(Path(os.environ.get("WASM_RUNTIME", "build/wasm")) / "runtime.wasm")
        with tempfile.TemporaryDirectory() as directory:
            binary, out, err = [Path(directory) / name for name in ("program.wasm", "out", "err")]
            for fixture in ("containers/tuple_runtime_object_compare", "containers/dict_user_hash",
                            "classes/object_containers", "generics/template_empty_forward",
                            "classes/builtin_dict_basic", "classes/builtin_list_token_list",
                            "reflection/callables", "exceptions/exc_class_values", "generators/gen_resume_typed_iterators",
                            "generators/gen_suspend_temporaries", "generators/gen_protocol_noeh", "generators/gen_resume_depth",
                            "library/lib_atexit", "library/lib_atexit_exit", "library/lib_atexit_uncaught"):
                with self.subTest(fixture=fixture):
                    source = Path("tests/programs") / (fixture + ".py")
                    subprocess.run(["wasm/build.sh", "direct", source, binary], check=True,
                                   env={**os.environ, "WASM_EH": "standard"})
                    program = runner.compile(binary.read_bytes())
                    self.assertIsNotNone(program.data_size)
                    status = runner.run(program, stdout=out, stderr=err)
                    self.assertEqual(out.read_bytes() + f"[exit {status}]\n".encode(),
                                     source.with_suffix(".out").read_bytes())
                    expected_error = source.with_suffix(".err")
                    expected = expected_error.read_bytes() if expected_error.exists() else b""
                    if source.stem == "lib_atexit":
                        expected = (b"Exception ignored in atexit callback:\nSystemExit: 3\n"
                                    b"Exception ignored in atexit callback:\n" + expected)
                    self.assertEqual(err.read_bytes(), expected)
