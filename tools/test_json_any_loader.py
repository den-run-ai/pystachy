"""JSON helper routing must preserve user modules without shadowing test imports."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = '''# pystachy: dynamic-any
from typing import Any
import json

value: Any = json.loads("1")
print(value)
print(json.dumps(value))
'''
USER_JSON = '''def loads(s: str) -> int:
    return 42

def dumps(value) -> str:
    return "user json"
'''


class JsonAnyLoaderTests(unittest.TestCase):
    def compile(self, directory, source, search_path=""):
        program = directory / "program.py"
        program.write_text(source)
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYSTACHY_")}
        env["PYSTACHY_HOME"] = str(ROOT)
        env["PYSTACHY_PATH"] = str(search_path)
        env["PYSTACHY_IRCHECK"] = "1"
        result = subprocess.run(
            [sys.executable, str(ROOT / "pystachy.py"), "ir", str(program)],
            env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def check_user_module(self, from_search_path):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            modules = directory / "modules" if from_search_path else directory
            modules.mkdir(exist_ok=True)
            (modules / "json.py").write_text(USER_JSON)
            ir = self.compile(directory, PROGRAM, modules if from_search_path else "")
            self.assertNotIn("_pystachy_json_any", ir)
            self.assertIn("user json", ir)

    def test_program_local_json_keeps_its_functions(self):
        self.check_user_module(False)

    def test_search_path_json_keeps_its_functions(self):
        self.check_user_module(True)

    def test_bundled_json_uses_dynamic_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir = self.compile(Path(tmp), PROGRAM)
            self.assertIn("_pystachy_json_any$loads", ir)
            self.assertIn("_pystachy_json_any$dumps", ir)

    def test_typed_json_keeps_typed_functions(self):
        with tempfile.TemporaryDirectory() as tmp:
            ir = self.compile(Path(tmp), 'import json\nprint(json.loads("1"))\n')
            self.assertNotIn("_pystachy_json_any", ir)


if __name__ == "__main__":
    unittest.main()
