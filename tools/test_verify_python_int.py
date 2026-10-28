"""The promoting-int shell stage needs complete evidence from its verified compiler."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_merge_verification import COMPILER_BYTES, python_int_report

ROOT = Path(__file__).resolve().parent.parent
STAGE = (ROOT / "tests/verify.sh").read_text().split("# ---- python-int-optin:", 1)[1].split("# ---- re-probe:", 1)[0]


class PythonIntStageTests(unittest.TestCase):
    def run_stage(self, evidence, status=0, compiler=COMPILER_BYTES, ci=True):
        # CI's groups (VERIFY_BOOTSTRAP_DIR) defer to tests-native; a local single group does not.
        mode = ({"VERIFY_BOOTSTRAP_DIR": "bundle", "GROUP": "python-int-optin-0", "MOCK_NATIVE": "--native-suite ",
                 "MOCK_ARGS": "17"} if ci else
                {"VERIFY_BOOTSTRAP_DIR": "", "GROUP": "python-int-optin-0", "MOCK_NATIVE": "", "MOCK_ARGS": "16"})
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "pystachy2").write_bytes(compiler)
            source = directory / "evidence.json"
            source.write_text(json.dumps(evidence))
            wrapper = directory / "python-wrapper"
            wrapper.write_text('''#!/bin/sh
if [ "$1" = tools/python_int_gate.py ]; then
  [ "$*" = "tools/python_int_gate.py --compiler $V/pystachy2 --modes jit aot $MOCK_NATIVE--jobs 2 \
--shard-index 0 --shard-count 4 --report $V/python-int-optin-0.json --keep $V/python-int-optin-0" ] &&
    [ "$#" = "$MOCK_ARGS" ] || exit 99
  cp "$MOCK_EVIDENCE" "$V/python-int-optin-0.json"
  exit "$MOCK_STATUS"
fi
exec "$REAL_PYTHON" "$@"
''')
            wrapper.chmod(0o755)
            script = '''want() { [ "$1" = python-int-optin-0 ]; }
now() { echo 0; }
step() { printf '{"name":"%s", "result":"%s"%s}\n' "$1" "$2" "$5"; }
''' + STAGE
            process = subprocess.run(["sh", "-c", script], cwd=ROOT,
                                     env={**os.environ, "V": temp, "PY": str(wrapper),
                                          "PYSTACHY_JOBS": "2", "MOCK_EVIDENCE": str(source),
                                          "MOCK_STATUS": str(status), "REAL_PYTHON": sys.executable, **mode},
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(process.stdout)

    def test_success_requires_full_evidence_and_the_executed_compiler(self):
        evidence = python_int_report(0)
        self.assertEqual(self.run_stage(evidence),
                         {"name": "python-int-optin-0", "result": "pass", "python_int_optin": evidence})
        self.assertEqual(self.run_stage(evidence, compiler=b"another compiler")["result"], "fail")
        # A local group, without tests-native, executes every check itself.
        self.assertEqual(self.run_stage(evidence, ci=False)["result"], "fail")
        local = {**copy.deepcopy(evidence), "native_suite": False}
        self.assertEqual(self.run_stage(local, ci=False)["result"], "pass")
        self.assertEqual(self.run_stage(local)["result"], "fail")

    def test_incomplete_exploratory_wrong_mode_or_failed_runs_fail(self):
        valid = python_int_report(0)
        cases = [(valid, 1), ({}, 0)]
        for key, value in (("oracle_cases", 0), ("subset", True), ("modes", ["jit"]),
                           ("results", []), ("shard_index", 1), ("shard_count", 8),
                           ("gc_stress", True), ("python", "3.13.0"),
                           ("source_sha256", "0" * 64), ("failures", ["lost result"])):
            evidence = copy.deepcopy(valid)
            evidence[key] = value
            cases.append((evidence, 0))
        for evidence, status in cases:
            with self.subTest(status=status, keys=list(evidence)):
                self.assertEqual(self.run_stage(evidence, status)["result"], "fail")


if __name__ == "__main__":
    unittest.main()
