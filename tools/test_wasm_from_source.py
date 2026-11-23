"""The source frontend and the printed IR path must feed the same Wasm emitter."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools import typed_ir_text
from wasm.tir_wasm import Emitter, parse

ROOT = Path(__file__).resolve().parent.parent


def source_command(*args, stdin=None, cwd=ROOT, eh="legacy"):
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYSTACHY_HOME=str(ROOT), PYTHONIOENCODING="utf-8", WASM_EH=eh)
    env.pop("WASM_GUEST_ROOTS", None)   # (the default: guest roots, which the expected modules below name)
    return subprocess.run([sys.executable, str(ROOT / "tools/wasm_from_source.py"), *args],
                          cwd=cwd, env=env, input=stdin, capture_output=True, timeout=30)


class WasmSourceTests(unittest.TestCase):
    def test_direct_and_printed_ir_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            for case in ("apps/ouro2_hello", "apps/ouro2_classes", "apps/ouro2_queens", "exceptions/exc_uncaught",
                         "exceptions/exc_class_try", "exceptions/exc_class_exit",
                         "classes/object_containers", "classes/dataclass_hash_keys",
                         "reflection/callables", "exceptions/exc_class_values", "generators/gen_protocol_noeh"):
                with self.subTest(case=case):
                    program = ROOT / f"tests/programs/{case}.py"
                    work = Path(directory) / program.stem
                    work.mkdir()
                    report, snapshot, _ = typed_ir_text.inspected(program, work)
                    self.assertEqual(report["status"], "ok")
                    printed = typed_ir_text.format_module(typed_ir_text.module_from_snapshot(snapshot))
                    expected = bytes(Emitter(parse(printed), False, True).module())
                    result = source_command(program, "-")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, expected)

    def test_standard_and_legacy_handlers_from_source_and_text(self):
        program = ROOT / "tests/programs/exceptions/exc_raise.py"
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            _, snapshot, _ = typed_ir_text.inspected(program, work)
            printed = typed_ir_text.format_module(typed_ir_text.module_from_snapshot(snapshot))
            outputs = []
            for encoding in ("legacy", "standard"):
                expected = bytes(Emitter(parse(printed), encoding == "standard", True).module())
                result = source_command(program, "-", eh=encoding)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, expected)
                outputs.append(expected)
            self.assertNotEqual(*outputs)
            invalid = source_command(program, "-", "-", eh="invalid")
            self.assertEqual(invalid.returncode, 2)
            self.assertIn(b"WASM_EH", invalid.stderr)
            self.assertEqual(invalid.stdout, b"")

    def test_refusal_reuses_finalized_ir_and_frontend_errors_stay_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            program = work / "test.py"
            wasm = work / "out.wasm"
            fallback = work / "fallback.ll"
            program.write_text('def numbers():\n    try:\n        yield "é雪🌲"\n    finally:\n        print("", end="")\n'
                               'for n in numbers():\n    print(n)\n', encoding="utf-8")
            result = source_command(program, wasm, fallback)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertIn(b"refused:", result.stderr)
            self.assertFalse(wasm.exists())
            reference = work / "reference.ll"
            subprocess.run([sys.executable, "pystachy.py", "ir", str(program), "-o", str(reference)],
                           cwd=ROOT, capture_output=True, check=True)
            self.assertEqual(fallback.read_bytes(), reference.read_bytes())
            self.assertEqual(result.stdout, b"")
            streamed = source_command(program, "-", "-")
            self.assertEqual(streamed.returncode, 3, streamed.stderr)
            self.assertEqual(streamed.stderr, result.stderr)
            self.assertEqual(streamed.stdout, reference.read_bytes())
            fallback.unlink()
            program.write_text("def broken(:\n")
            result = source_command(program, wasm, fallback)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(wasm.exists())
            self.assertFalse(fallback.exists())
            streamed = source_command(program, "-", "-")
            self.assertEqual(streamed.returncode, 1, streamed.stderr)
            self.assertEqual(streamed.stdout, b"")

    def test_stdio_preserves_unicode_and_resolves_sibling_imports(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "helper.py").write_text('def word() -> str:\n    return "雪"\n')
            source = 'from helper import word\nprint(word(), "é")\n'.encode()
            # A real file with the virtual diagnostic name cannot redirect imports.
            shadow = work / "other"
            shadow.mkdir()
            (work / "<codemode>.py").symlink_to(shadow / "script.py")
            virtual = source_command("-", "-", "-", stdin=source, cwd=work)
            self.assertEqual(virtual.returncode, 0, virtual.stderr)
            # Compile the same logical path on disk to check source encoding and names.
            (work / "<codemode>.py").unlink()
            (work / "<codemode>.py").write_bytes(source)
            written = source_command("<codemode>.py", "-", cwd=work)
            self.assertEqual(written.returncode, 0, written.stderr)
            self.assertEqual(virtual.stdout, written.stdout)
            self.assertIn("雪".encode(), written.stdout)


if __name__ == "__main__":
    unittest.main()
