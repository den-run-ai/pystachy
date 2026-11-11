"""Select the dynamic-Any corpus as the compiler reaches it, and check programs with Lean."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import check_lean_corpus as corpus

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "tools" / "lean_boundary" / ".lake" / "build" / "bin" / "pystachy-boundary"
TOOL = ROOT / "tools" / "check_lean_corpus.py"
PRAGMA = "# pystachy: dynamic-any\n"

if os.environ.get("LEAN_BOUNDARY_REQUIRED") == "1" and not CHECKER.is_file():
    raise RuntimeError("Lean boundary checker is required; build tools/lean_boundary first")


class ReachTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.directories = [self.base / "programs", self.base / "helpers", self.base / "lib"]
        files = {
            "lib/dynlib/__init__.py": "from dynlib import _impl\n",
            "lib/dynlib/_impl.py": PRAGMA + "x = 1\n",
            "lib/plain.py": "import os\n",
            "helpers/pkg/__init__.py": "",
            "helpers/pkg/opted.py": PRAGMA + "x = 1\n",
            "helpers/pkg/typed.py": "from . import sibling\n",
            "helpers/pkg/sibling.py": "",
            "helpers/pkg/relative.py": "from .opted import x\n",
            "helpers/cycle_a.py": "import cycle_b\n",
            "helpers/cycle_b.py": "import cycle_a\n",
        }
        for name, text in files.items():
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def test_opt_ins_and_the_modules_a_program_reaches(self):
        cases = {
            PRAGMA + "print(1)\n": True,
            "import plain\n": False,
            # (through the package's __init__.py, which imports its opted-in module)
            "import dynlib\n": True,
            # another module of a package that has one does not opt in
            "from pkg import typed\n": False,
            "import pkg.sibling\n": False,
            # a name imported from a package may be its submodule
            "from pkg import opted\n": True,
            "import pkg.relative\n": True,
            "def f():\n    import pkg.opted\n": True,
            "import cycle_a\n": False,
            "import missing\n": False,
            "﻿import plain\n": False,
            # (an unparsable file is compiled anyway)
            "def broken(:\n": True,
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                program = self.directories[0] / "case.py"
                program.parent.mkdir(exist_ok=True)
                program.write_text(source)
                self.assertEqual(corpus.Reach().dynamic(program, self.directories), expected)

    def test_search_path_is_the_programs_directory_its_path_file_then_lib(self):
        program = ROOT / "tests/programs/inference/dynany_identity_promote_module.py"
        self.assertEqual(corpus.search_path(program),
                         [program.parent, ROOT / "tests/dynany_promote_support", ROOT / "lib"])


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selected = corpus.select()

    def test_corpus_selection_covers_each_way_to_reach_dynamic_code(self):
        for program in ("tests/programs/inference/dynany_slices.py",
                        "tests/programs/upstream/upstream_tomllib_misc.py",
                        "tests/programs/inference/dynany_identity_promote_module.py",
                        "tests/deviations/dynany_abs_overflow.py"):
            with self.subTest(program=program):
                self.assertIn(program, self.selected)
        self.assertNotIn("tests/programs/strings/bom.py", self.selected)
        self.assertEqual(self.selected, sorted(self.selected, key=lambda name: name.encode()))
        self.assertTrue(all(name.startswith(("tests/programs/", "tests/deviations/")) for name in self.selected))
        self.assertGreater(len(self.selected), 400)


@unittest.skipUnless(CHECKER.is_file(), "build tools/lean_boundary to run the proved checker")
class CorpusRunTests(unittest.TestCase):
    def run_tool(self, *programs):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        report = Path(temporary.name) / "report.json"
        completed = subprocess.run([sys.executable, str(TOOL), "--report", str(report), "--jobs", "2", *programs],
                                   cwd=ROOT, capture_output=True, text=True, timeout=600)
        return completed, json.loads(report.read_text())

    def test_named_programs_are_inspected_and_every_read_is_proved(self):
        completed, report = self.run_tool("tests/programs/inference/dynany_slices.py",
                                          "tests/programs/strings/bom.py")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(report["status"], "accepted")
        records = {record["program"]: record for record in report["programs"]}
        dynamic = records["tests/programs/inference/dynany_slices.py"]["totals"]
        self.assertGreater(dynamic["reads"], 0)
        self.assertEqual(dynamic["proved_reads"], dynamic["reads"])
        self.assertEqual(records["tests/programs/strings/bom.py"]["totals"]["reads"], 0)
        self.assertEqual(report["totals"]["programs"], 2)
        self.assertIn("2 programs", completed.stdout)

    def test_a_program_that_does_not_compile_fails_the_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            program = Path(temporary) / "broken.py"
            program.write_text(PRAGMA + "def broken(:\n")
            completed, report = self.run_tool(str(program))
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        self.assertEqual(report["status"], "error")
        self.assertIn("error: ", completed.stdout)



class CommandTests(unittest.TestCase):
    def test_a_missing_checker_or_no_worker_is_an_error(self):
        for arguments, code in ((["--checker", str(ROOT / "missing-checker")], 3), (["--jobs", "0"], 2)):
            with self.subTest(arguments=arguments):
                completed = subprocess.run([sys.executable, str(TOOL), *arguments,
                                            "tests/programs/inference/dynany_slices.py"],
                                           cwd=ROOT, capture_output=True, text=True, timeout=60)
                self.assertEqual(completed.returncode, code, completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main()
