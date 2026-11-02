"""Terminal diagnostic records preserve the compiler's existing rejection contract."""
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.emission import gen_err


ROOT = Path(__file__).resolve().parent.parent


class DiagnosticCaptureTests(unittest.TestCase):
    def setUp(self):
        self.state = patch.multiple(diagnostics, SRC="main.py", FILES=[],
                                    CAPTURE=False, CAPTURED=[], PHASE="compile")
        self.state.start()
        self.addCleanup(self.state.stop)

    def fail(self, message, line, context=None):
        output = StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as caught:
            diagnostics.fail(message, line, context)
        self.assertEqual(caught.exception.code, 1)
        return output.getvalue()

    def test_default_text_and_exit_do_not_capture(self):
        self.assertEqual(self.fail("name '__main__$missing' is not defined", 7),
                         "main.py:7: error: name 'missing' is not defined\n")
        self.assertEqual(diagnostics.CAPTURED, [])

    def test_capture_preserves_text_and_raw_json_characters(self):
        diagnostics.SRC = 'dir:part/quoted"-é.py'
        message = 'unexpected "value"\\path\nnext\tline\x00'
        expected = self.fail(message, 12)
        diagnostics.CAPTURE = True
        diagnostics.PHASE = "parse"
        self.assertEqual(self.fail(message, 12), expected)
        self.assertEqual(len(diagnostics.CAPTURED), 1)
        record = vars(diagnostics.CAPTURED[0])
        self.assertEqual(record, {"code": "PYS0001", "severity": "error", "phase": "parse",
                                  "message": message, "file": diagnostics.SRC,
                                  "line": 12, "context": []})
        self.assertEqual(json.loads(json.dumps(record)), record)

    def test_import_location_uses_file_index_not_colon_splitting(self):
        diagnostics.CAPTURE = True
        diagnostics.PHASE = "semantic"
        diagnostics.FILES[:] = ["main.py", "dir:with:colons/helper.py"]
        text = self.fail("name 'missing' is not defined", diagnostics.LINES + 23)
        record = diagnostics.CAPTURED[0]
        self.assertEqual(record.file, "dir:with:colons/helper.py")
        self.assertEqual(record.line, 23)
        self.assertEqual(text, f"{record.file}:23: error: {record.message}\n")
        # The next Loader.program owns another file-index space. An existing
        # diagnostic keeps its resolved source identity rather than that index.
        diagnostics.FILES[:] = ["next.py", "next-import.py"]
        diagnostics.SRC = "next.py"
        self.assertEqual(record.file, "dir:with:colons/helper.py")

    def test_internal_error_and_absent_source_line_remain_explicit(self):
        diagnostics.CAPTURE = True
        diagnostics.PHASE = "verify"
        self.fail("internal error: missing typed operation", 0)
        record = diagnostics.CAPTURED[0]
        self.assertEqual((record.code, record.phase, record.line), ("PYS9000", "verify", 0))
        self.assertEqual(record.file, "main.py")

    def test_context_is_copied_and_names_are_shown(self):
        diagnostics.CAPTURE = True
        notes = ["compiling __main__$outer(int)", "compiling helper$inner(int)"]
        self.fail("unsupported operand", 4, notes)
        notes.clear()
        self.assertEqual(diagnostics.CAPTURED[0].context,
                         ["compiling outer(int)", "compiling helper.inner(int)"])

    def generator(self, **changes):
        values = dict(xtry="", newx={}, newhints={}, final=False, making=[], recursive=[], line=4)
        values.update(changes)
        return SimpleNamespace(**values)

    def test_speculative_retry_paths_capture_no_terminal_error(self):
        diagnostics.CAPTURE = True
        for generator in (self.generator(xtry="comparison"),
                          self.generator(newhints={"local": "int | str"})):
            with self.subTest(generator=generator), redirect_stderr(StringIO()) as output:
                with self.assertRaises(diagnostics.Rejoin):
                    gen_err(generator, "tentative mismatch")
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(diagnostics.CAPTURED, [])
        self.assertEqual(generator.newhints, {"local": "int | str"})

    def test_terminal_specialization_context_matches_legacy_message(self):
        diagnostics.CAPTURE = True
        diagnostics.PHASE = "semantic"
        notes = ["compiling outer(int) for the call at main.py:9",
                 "compiling inner(int) for the call at main.py:6"]
        generator = self.generator(making=notes, newhints={"local": "str"}, final=True)
        with redirect_stderr(StringIO()) as output, self.assertRaises(SystemExit) as caught:
            gen_err(generator, "expected int, got str")
        self.assertEqual(caught.exception.code, 1)
        expected = "expected int, got str (" + "; ".join(reversed(notes)) + ")"
        self.assertEqual(output.getvalue(), f"main.py:4: error: {expected}\n")
        self.assertEqual(diagnostics.CAPTURED[0].message, expected)
        self.assertEqual(diagnostics.CAPTURED[0].context, notes)

    def test_real_compilation_keeps_output_and_context(self):
        # Each compilation has its own worker: these tests do not imply that the
        # compiler's other process-global tables support concurrent/reused sessions.
        script = '''
from contextlib import redirect_stderr
from io import StringIO
import json
import sys
from src.pystachy_compiler import diagnostics, driver
diagnostics.SRC = "specialize.py"
diagnostics.CAPTURE = sys.argv[1] == "capture"
diagnostics.PHASE = "semantic"
source = "def inner(value):\\n    return value + 'x'\\ndef outer(value):\\n    return inner(value)\\nouter(1)\\n"
with redirect_stderr(StringIO()) as output:
    try:
        driver.compile_program("specialize.py", source, [], "")
    except SystemExit as failure:
        code = failure.code
    else:
        raise AssertionError("invalid source unexpectedly compiled")
print(json.dumps({"code": code, "stderr": output.getvalue(),
                  "diagnostics": [vars(d) for d in diagnostics.CAPTURED]}))
'''
        results = []
        for mode in ("plain", "capture"):
            process = subprocess.run([sys.executable, "-c", script, mode], cwd=ROOT,
                                     text=True, capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            results.append(json.loads(process.stdout))
        plain, captured = results
        self.assertEqual(plain["diagnostics"], [])
        self.assertEqual((plain["code"], plain["stderr"]),
                         (captured["code"], captured["stderr"]))
        self.assertEqual(len(captured["diagnostics"]), 1)
        record = captured["diagnostics"][0]
        self.assertEqual((record["file"], record["line"]), ("specialize.py", 2))
        self.assertEqual(len(record["context"]), 2)
        self.assertIn("compiling outer(int)", record["context"][0])
        self.assertIn("compiling inner(int)", record["context"][1])


if __name__ == "__main__":
    unittest.main()
