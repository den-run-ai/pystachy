"""Cache checks require successful execution as well as matching output/builds."""
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


class CacheCheckTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        source = (ROOT / "tests/cache.sh").read_text()
        start = source.index("\ncheck() {\n")
        self.check = source[start:source.index("\nsame()", start)]
        self.root.joinpath("prog.py").write_text('print("runtime ready")\nprint(42)\n')
        compiler = self.root / "compiler"
        compiler.write_text('''#!/bin/sh
[ "$1" = run ] && [ -f "$2" ] || exit 98
printf 'runtime ready\\n42\\n'
exit "$CACHE_PROBE_STATUS"
''')
        compiler.chmod(0o755)

    def run_check(self, status, byname):
        # Execute the production helper without building LLVM or copying the
        # cache suite. A run can print every expected byte before failing.
        script = '''
pass=0; fail=0
H="$T/home"; PY=; me=./compiler
builds() { echo 1; }
pys() { (cd "$T" && ./compiler "$@"); }
ok() { pass=$((pass + 1)); echo "ok   $1"; }
bad() { fail=$((fail + 1)); echo "FAIL $1"; }
''' + self.check + '''
expected=$(printf 'runtime ready\\n42')
check probe "$expected" 0
echo "$pass passed, $fail failed"
[ "$fail" = 0 ]
'''
        return subprocess.run(
            ["sh", "-c", script], cwd=self.root, text=True, capture_output=True, timeout=10,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "T": str(self.root),
                 "BYNAME": str(self.root) if byname else "", "CACHE_PROBE_STATUS": str(status)})

    def test_matching_output_and_builds_cannot_hide_a_failed_run(self):
        for byname in (False, True):
            with self.subTest(byname=byname):
                result = self.run_check(23, byname)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("FAIL probe: exited 23", result.stdout)
                self.assertIn("runtime ready\n42", result.stdout)
                self.assertIn("0 passed, 1 failed", result.stdout)
                self.assertEqual(result.stderr, "")

    def test_successful_run_still_passes_with_matching_output_and_builds(self):
        for byname in (False, True):
            with self.subTest(byname=byname):
                result = self.run_check(0, byname)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("ok   probe", result.stdout)
                self.assertIn("1 passed, 0 failed", result.stdout)
                self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
