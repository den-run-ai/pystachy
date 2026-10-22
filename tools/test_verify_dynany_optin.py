"""Exercise the real shell stage: a successful process is not sufficient evidence."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_merge_verification import optin_report

ROOT = Path(__file__).resolve().parent.parent
STAGE = (ROOT / "tests/verify.sh").read_text().split("# ---- dynany-optin:", 1)[1].split("# ---- re-probe:", 1)[0]


class DynanyOptinStageTests(unittest.TestCase):
    def run_stage(self, evidence, status=0):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            source = directory / "evidence.json"
            source.write_text(json.dumps(evidence))
            wrapper = directory / "python-wrapper"
            wrapper.write_text('''#!/bin/sh
if [ "$1" = tools/dynany_optin.py ]; then
  [ "$2" = --compiler ] && [ "$3" = "$V/pystachy2" ] &&
    [ "$4" = --modes ] && [ "$5" = jit ] && [ "$6" = aot ] &&
    [ "$7" = --jobs ] && [ "$8" = 2 ] &&
    [ "$9" = --shard-index ] && [ "${10}" = 0 ] &&
    [ "${11}" = --shard-count ] && [ "${12}" = 4 ] &&
    [ "${13}" = --report ] && [ "${14}" = "$V/dynany-optin-0.json" ] &&
    [ "${15}" = --keep ] && [ "${16}" = "$V/dynany-optin-0" ] &&
    [ "$#" = 16 ] || exit 99
  cp "$MOCK_EVIDENCE" "$V/dynany-optin-0.json"
  exit "$MOCK_STATUS"
fi
exec "$REAL_PYTHON" "$@"
''')
            wrapper.chmod(0o755)
            script = '''want() { [ "$1" = dynany-optin-0 ]; }
now() { echo 0; }
step() { printf '{"name":"%s", "result":"%s"%s}\n' "$1" "$2" "$5"; }
''' + STAGE
            process = subprocess.run(["sh", "-c", script], cwd=ROOT,
                                     env={**os.environ, "V": temp, "PY": str(wrapper),
                                          "PYSTACHY_JOBS": "2", "MOCK_EVIDENCE": str(source),
                                          "MOCK_STATUS": str(status), "REAL_PYTHON": sys.executable},
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            return json.loads(process.stdout)

    def test_success_requires_valid_full_evidence(self):
        evidence = optin_report(0)
        result = self.run_stage(evidence)
        self.assertEqual(result, {"name": "dynany-optin-0", "result": "pass", "optin": evidence})

    def test_partial_wrong_mode_or_failed_runs_fail(self):
        valid = optin_report(0)
        cases = [(valid, 1), ({}, 0)]
        for key, value in (("oracle_cases", 0), ("subset", True), ("modes", ["jit"]),
                           ("results", []), ("shard_index", 1), ("failures", ["lost result"])):
            evidence = copy.deepcopy(valid)
            evidence[key] = value
            cases.append((evidence, 0))
        for evidence, status in cases:
            with self.subTest(status=status, keys=list(evidence)):
                self.assertEqual(self.run_stage(evidence, status)["result"], "fail")


if __name__ == "__main__":
    unittest.main()
