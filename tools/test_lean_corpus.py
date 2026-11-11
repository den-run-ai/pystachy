"""Select the dynamic-Any corpus as the compiler reaches it, and check programs with Lean.

make check-lean-corpus runs these before the corpus itself, in CI's opt-in verification group:
they are not among Lint's test_lean_boundary*.py tests, whose job is at its time bound."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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
            # namespace packages: directories without __init__.py, one split across two
            # directories of the search path
            "helpers/ns/helper.py": PRAGMA + "x = 1\n",
            "helpers/ns/plainmod.py": "",
            "helpers/ns/deeper/inner.py": PRAGMA + "x = 1\n",
            "helpers/split/part_a.py": "",
            "lib/split/part_b.py": PRAGMA + "x = 1\n",
        }
        for name, text in files.items():
            path = self.base / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def test_opt_ins_and_the_modules_a_program_reaches(self):
        cases = {
            PRAGMA + "print(1)\n": True,
            "\ufeff" + PRAGMA + "print(1)\n": True,
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
            # (loader.py's filepath: a directory without __init__.py is a namespace package)
            "import ns.helper\n": True,
            "from ns import helper\n": True,
            "import ns.deeper.inner\n": True,
            "from ns.deeper import inner\n": True,
            "import ns.plainmod\n": False,
            "import ns\n": False,
            "import split.part_b\n": True,
            "import split.part_a\n": False,
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


class AccountingTests(unittest.TestCase):
    def run_report(self, status, payloads=0):
        """Exercise program and corpus accounting without compiling or running Lean."""
        payload = {"status": "accepted", "functions": [{"function": "@payload", "status": "accepted"}] * payloads,
                   "totals": {"functions": 1 + payloads, "payload_functions": payloads,
                              "reads": payloads, "proved_reads": payloads,
                              "accepted": payloads, "unsupported": 0, "rejected": 0, "error": 0}}
        accesses = {"status": status, "functions": [{"function": "@access", "status": status}],
                    "totals": {"access_functions": 1, "accesses": 1,
                               "proved_accesses": int(status == "accepted"),
                               **{name: int(name == status) for name in corpus.bridge.SEVERITY}}}

        def inspect(command, **kwargs):
            output = Path(command[command.index("--output") + 1])
            output.mkdir()
            (output / "report.json").write_text(json.dumps({"status": "ok"}))
            (output / "typed-after.json").write_text(json.dumps(
                {"schema_version": 1, "stage": "typed-after", "status": "completed", "functions": []}))
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            checker = base / "checker"
            checker.touch()
            report = base / "report.json"
            with (mock.patch.object(corpus.subprocess, "run", side_effect=inspect),
                  mock.patch.object(corpus.bridge, "check_all", return_value=(payload, 0)),
                  mock.patch.object(corpus.access, "check_all", return_value=(accesses, corpus.bridge.OUTCOMES[status])),
                  redirect_stdout(io.StringIO())):
                code = corpus.main(["--checker", str(checker), "--access-checker", str(checker),
                                    "--report", str(report), "--jobs", "1",
                                    str(base / "first.py"), str(base / "second.py")])
            return code, json.loads(report.read_text())

    def test_access_only_statuses_reach_program_and_corpus_totals(self):
        for status, expected_code in (("accepted", 0), ("rejected", 1), ("unsupported", 2), ("error", 3)):
            with self.subTest(status=status):
                code, report = self.run_report(status)
                self.assertEqual((code, report["status"]), (expected_code, status))
                self.assertEqual(report["totals"]["failed_programs"], 0 if status == "accepted" else 2)
                records = [(report["totals"], 2)] + [(record["totals"], 1) for record in report["programs"]]
                for totals, count in records:
                    self.assertEqual(totals["payload_functions"], 0)
                    self.assertEqual(totals["access_functions"], count)
                    self.assertEqual(totals["proved_accesses"], count if status == "accepted" else 0)
                    for name in corpus.bridge.SEVERITY:
                        self.assertEqual(totals[name], 0)  # existing counters describe payload functions
                        self.assertEqual(totals["access_" + name], count if name == status else 0)
                for record in report["programs"]:
                    self.assertEqual([failure["status"] for failure in record["failures"]],
                                     [] if status == "accepted" else [status])

    def test_payload_acceptances_remain_separate_from_access_rejections(self):
        code, report = self.run_report("rejected", payloads=1)
        self.assertEqual(code, 1)
        for totals, count in [(report["totals"], 2)] + [(record["totals"], 1) for record in report["programs"]]:
            self.assertEqual(totals["accepted"], count)
            self.assertEqual(totals["rejected"], 0)
            self.assertEqual(totals["access_accepted"], 0)
            self.assertEqual(totals["access_rejected"], count)


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
                                          "tests/programs/strings/bom.py",
                                          "tools/lean_boundary/examples/unchecked_accesses.py")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(report["status"], "accepted")
        records = {record["program"]: record for record in report["programs"]}
        dynamic = records["tests/programs/inference/dynany_slices.py"]["totals"]
        self.assertGreater(dynamic["reads"], 0)
        self.assertEqual(dynamic["proved_reads"], dynamic["reads"])
        # (the same snapshots' unchecked list reads and dict entries are proved too)
        accesses = records["tools/lean_boundary/examples/unchecked_accesses.py"]["totals"]
        self.assertGreater(accesses["accesses"], 0)
        self.assertEqual(report["totals"]["proved_accesses"], report["totals"]["accesses"])
        self.assertEqual(records["tests/programs/strings/bom.py"]["totals"]["reads"], 0)
        self.assertEqual(report["totals"]["programs"], 3)
        self.assertIn("3 programs", completed.stdout)
        self.assertIn("unchecked accesses proved", completed.stdout)

    def test_a_namespace_packages_dynamic_module_is_selected_and_proved(self):
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "ns").mkdir()
            (Path(temporary) / "ns" / "helper.py").write_text(
                PRAGMA + "from typing import Any\n\n\ndef describe(x: Any) -> str:\n"
                "    if isinstance(x, str):\n        return 'str ' + x\n    return 'other'\n")
            program = str(Path(temporary) / "uses_namespace.py")
            Path(program).write_text("import ns.helper\n\nprint(ns.helper.describe('a'))\n"
                                     "print(ns.helper.describe(1))\n")
            self.assertEqual(corpus.select([program]), [program])
            completed, report = self.run_tool(program)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        totals = report["programs"][0]["totals"]
        self.assertGreater(totals["reads"], 0)
        self.assertEqual(totals["proved_reads"], totals["reads"])

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
