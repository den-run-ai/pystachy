"""Runtime-only module configuration must not escape its compilation scope."""
import inspect
import subprocess
import sys
import unittest
from unittest.mock import patch

from compiler_state_probe import ROOT
from src.pystachy_compiler import driver


class RuntimeStateTests(unittest.TestCase):
    def runtime_contract(self, runtime_ir):
        # Exercise the production boundary with failures at each operation after
        # the temporary configuration is installed. Preserve absent and false
        # entries separately: presence, not truth, controls builtin imports.
        for previous in (None, False, True):
            for failure in ("", "loader_init", "loader_program", "gen_program"):
                for exception in (RuntimeError, SystemExit):
                    with self.subTest(previous=previous, failure=failure, exception=exception.__name__):
                        self.runtime_case(runtime_ir, previous, failure, exception)

    def runtime_case(self, runtime_ir, previous, failure, exception):
        modules = driver.MODULES
        saved = modules.copy()
        modules.pop("_rt", None)
        if previous is not None:
            modules["_rt"] = previous
        before = list(modules.items())
        error = exception("scope failure")
        test = self

        def stage(name):
            test.assertIs(driver.MODULES, modules)
            test.assertIs(modules["_rt"], True)
            if name == failure:
                raise error

        class FakeLoader:
            def __init__(self, dirs):
                stage("loader_init")
                test.assertEqual(dirs, [])

            def program(self, path, source):
                stage("loader_program")
                test.assertTrue(self.rtmode)
                return source

        class FakeGen:
            def program(self, source):
                stage("gen_program")
                test.assertTrue(self.rtmode)
                test.assertTrue(self.rtcache)
                return "runtime IR"

        try:
            with patch.dict(runtime_ir.__globals__, Gen=FakeGen, Loader=FakeLoader):
                if failure:
                    with self.assertRaises(exception) as raised:
                        runtime_ir("probe.py", "source", True)
                    self.assertIs(raised.exception, error)
                else:
                    self.assertEqual(runtime_ir("probe.py", "source", True), "runtime IR")
            self.assertIs(driver.MODULES, modules)
            self.assertEqual(list(modules.items()), before)
        finally:
            modules.clear()
            modules.update(saved)
    def test_success_and_every_failure_restore_exact_configuration(self):
        self.runtime_contract(driver.runtime_ir)

    def test_missing_or_inexact_restoration_is_detected(self):
        source = inspect.getsource(driver.runtime_ir)
        mutations = (
            ("del MODULES[\"_rt\"]", "pass"),
            ("MODULES[\"_rt\"] = old_rt", "del MODULES[\"_rt\"]"),
            ("MODULES[\"_rt\"] = old_rt", "MODULES[\"_rt\"] = True"),
        )
        for before, after in mutations:
            with self.subTest(mutation=after):
                self.assertEqual(source.count(before), 1)
                namespace = dict(vars(driver))
                exec(compile(source.replace(before, after), "<runtime-scope-mutant>", "exec"), namespace)
                # Use a fresh TestCase: subTest captures assertion failures when
                # a unittest result is attached, which would hide the control.
                with self.assertRaises(AssertionError):
                    RuntimeStateTests().runtime_contract(namespace["runtime_ir"])

    def test_failed_runtime_compile_does_not_admit_internal_module(self):
        # The original leak used the real parser/compiler failure path: a failed
        # runtime compilation made a later ordinary 'import _rt' compile.
        script = '''
from contextlib import redirect_stderr
import io
from src.pystachy_compiler import driver

def rejected(action, expected):
    diagnostics = io.StringIO()
    with redirect_stderr(diagnostics):
        try:
            action()
        except SystemExit as error:
            assert error.code == 1
        else:
            raise AssertionError("unexpectedly accepted source")
    assert expected in diagnostics.getvalue(), diagnostics.getvalue()

before = list(driver.MODULES.items())
rejected(lambda: driver.runtime_ir("bad.py", "def pys_bad():\\n    return unknown\\n", False),
         "name 'unknown' is not defined")
assert list(driver.MODULES.items()) == before, "runtime module configuration leaked"
rejected(lambda: driver.compile_program("next.py", "import _rt\\nprint(1)\\n", [], ""),
         "module '_rt' is not supported")
assert "define" in driver.compile_program("valid.py", "print(1)\\n", [], "")
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, text=True,
                                capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
