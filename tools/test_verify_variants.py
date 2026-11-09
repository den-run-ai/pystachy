"""The variant runner covers current pass pairs and agrees with its CI matrix."""
import itertools
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.pystachy_compiler.specs import OPTS


ROOT = Path(__file__).resolve().parent.parent


class VariantTests(unittest.TestCase):
    def test_runner_covers_current_pass_pairs_and_matches_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("tools/variants.sh", "src/__init__.py", "src/pystachy_compiler/__init__.py",
                         "src/pystachy_compiler/specs.py", "src/pystachy_compiler/diagnostics.py",
                         "src/pystachy_compiler/names.py"):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            compiler = root / "compiler"
            compiler.write_text("#!/bin/sh\nexit 0\n")
            compiler.chmod(0o755)
            runner = root / "tests/run.sh"
            runner.parent.mkdir()
            runner.write_text('''#!/bin/sh
printf '%s|%s|%s|%s\\n' "${PYSTACHY_CACHE##*/}" "${PYSTACHY_OPT-}" "${PYSTACHY_CFLAGS-}" "${PYSTACHY_JIT_LAUNCHER-}" >> calls
echo '1 passed, 0 failed'
''')
            runner.chmod(0o755)
            result = subprocess.run(
                ["sh", "tools/variants.sh"], cwd=root, text=True, capture_output=True, timeout=20,
                env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PY": sys.executable,
                     "COMPILER": "./compiler"})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = [line.split("|") for line in (root / "calls").read_text().splitlines()]

        workflow = (ROOT / ".github/workflows/variants.yml").read_text()
        matrix = re.search(r"^\s+variant: \[([^\]]+)\]", workflow, re.M)
        self.assertIsNotNone(matrix)
        variants = matrix.group(1).replace(",", " ").split()
        # CI may reorder rows to balance work; each configuration must still run once.
        self.assertCountEqual([cache.removeprefix("cache-") for cache, _, _, _ in calls], variants)
        self.assertEqual(len(set(variants)), len(variants))
        rows = [{name: True for name in OPTS}]  # default all-on row, run by verification
        for cache, disabled, cflags, runner in calls:
            variant = cache.removeprefix("cache-")
            if variant == "cflags-O0":
                # (whose JIT runs in lli, the JIT runner's fallback, which every other row leaves alone)
                self.assertEqual((disabled, cflags, runner), ("", "-O0", "lli"))
                continue
            self.assertTrue(variant.startswith("opt-"), cache)
            self.assertEqual((cflags, runner), ("", ""))
            tokens = disabled.split(",") if disabled else []
            self.assertTrue(all(token.startswith("-") and token[1:] in OPTS for token in tokens), disabled)
            off = {token[1:] for token in tokens}
            rows.append({name: name not in off for name in OPTS})
        for name in OPTS:
            self.assertEqual({row[name] for row in rows}, {False, True}, name)
        for left, right in itertools.combinations(OPTS, 2):
            self.assertEqual({(row[left], row[right]) for row in rows},
                             {(False, False), (False, True), (True, False), (True, True)}, (left, right))

    def test_exhaustive_variants_stay_off_pull_requests(self):
        workflow = (ROOT / ".github/workflows/variants.yml").read_text()
        block = re.search(r"^  push:\n((?: {4,}.*\n|\n)+)", workflow, re.M)
        self.assertIsNotNone(block)
        self.assertIn("      - src/pystachy_compiler/specs.py\n", block.group(1))
        self.assertNotIn("  pull_request:", workflow)
        # PRs exercise all configurations on a sample in two workers in CI.
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        self.assertIn("tools/pr_variants.py", ci)


if __name__ == "__main__":
    unittest.main()
