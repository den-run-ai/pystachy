"""The real fuzzer verification stage must reject partial or unsuccessful runs."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
STAGE = (ROOT / "tests/verify.sh").read_text().split("# ---- dynany-fuzz:", 1)[1].split("# ---- re-probe:", 1)[0]
STAGE = STAGE[STAGE.index("if want dynany-fuzz;"):]


class DynanyFuzzStageTests(unittest.TestCase):
    def run_stage(self, summary, status=0):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            compiler = root / "mock-python"
            compiler.write_text('''#!/bin/sh
[ "$1" = tools/dynany_fuzz.py ] && [ "$2" = --compiler ] &&
  [ "$3" = "$V/pystachy2" ] && [ "$4" = --keep ] &&
  [ "$5" = "$V/dynany-fuzz" ] && [ "$6" = 3 ] && [ "$7" = 150 ] &&
  [ "$#" = 7 ] || exit 99
printf '%s\\n' "$MOCK_SUMMARY"
exit "$MOCK_STATUS"
''')
            compiler.chmod(0o755)
            script = '''want() { return 0; }
now() { echo 0; }
step() { printf '{"name":"%s", "result":"%s"%s}\\n' "$1" "$2" "$5"; }
''' + STAGE
            result = subprocess.run(["sh", "-c", script], cwd=root, capture_output=True, text=True,
                                    env={**os.environ, "V": temp, "PY": str(compiler),
                                         "MOCK_SUMMARY": summary, "MOCK_STATUS": str(status)}, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_native_compiler_budget_and_report(self):
        self.assertEqual(self.run_stage("3 programs, 450 cases (JIT): 0 mismatches"),
                         {"name": "dynany-fuzz", "result": "pass", "programs": 3,
                          "cases": 450, "modes": ["jit"], "mismatches": 0})

    def test_short_malformed_wrong_mode_mismatching_and_failed_runs(self):
        for summary, status in (("2 programs, 300 cases (JIT): 0 mismatches", 0),
                                ("3 programs, 449 cases (JIT): 0 mismatches", 0),
                                ("3 programs, 450 cases (JIT and AOT): 0 mismatches", 0),
                                ("3 programs, 450 cases (JIT): 5 mismatches", 0),
                                ("3 programs, 450 cases (JIT): 0 mismatches", 1),
                                ("", 0), ("unexpected output", 0)):
            with self.subTest(summary=summary, status=status):
                self.assertEqual(self.run_stage(summary, status)["result"], "fail")


if __name__ == "__main__":
    unittest.main()
