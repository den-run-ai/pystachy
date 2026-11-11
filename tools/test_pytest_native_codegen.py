"""Negative collection controls for the generated pytest dialect."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from pytest_native_codegen import CollectionError, generate


TOOLS = Path(__file__).resolve().parent


class CodegenControls(unittest.TestCase):
    def rejected(self, source, message):
        with self.assertRaisesRegex(CollectionError, message):
            generate(source, "test_input.py")

    def execute(self, source):
        generated = generate(source, "test_input.py")
        with tempfile.TemporaryDirectory() as directory:
            program = Path(directory) / "suite.py"
            report = Path(directory) / "report.jsonl"
            program.write_text(generated.source)
            process = subprocess.run(
                [sys.executable, str(program), str(report)], capture_output=True, text=True,
                env={**os.environ, "PYTHONPATH": str(TOOLS)}, timeout=20,
            )
            self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
            events = [json.loads(line) for line in report.read_text().splitlines()]
            self.assertTrue(events[-1]["complete"])
            return generated, events

    def test_xunit_hooks_never_disappear(self):
        for hook in ("setup_module", "setupModule", "teardown_module", "teardownModule",
                     "setup_function", "teardown_function"):
            with self.subTest(hook=hook):
                self.rejected(f"def {hook}():\n    assert False\ndef test_ok():\n    pass\n", "xunit")

    def test_import_time_helper_cannot_change_named_case_count(self):
        self.rejected("""import pytest
VALUES = [1]
def mutate():
    VALUES.append(2)
mutate()
@pytest.mark.parametrize('value', VALUES)
def test_value(value):
    assert value == 1
""", "static module initialization")

    def test_named_parameter_rebinding_and_mutation_are_rejected(self):
        for alteration in ("VALUES = [2, 3]", "VALUES[0] = 2", "VALUES += [2]"):
            with self.subTest(alteration=alteration):
                self.rejected("import pytest\nVALUES = [1]\n" + alteration + "\n"
                              "@pytest.mark.parametrize('value', VALUES)\n"
                              "def test_value(value):\n    assert value == 1\n",
                              "parametrize constants|static module initialization")

    def test_named_marker_mutation_cannot_hide_failure(self):
        self.rejected("""import pytest
SKIP = True
def mutate():
    global SKIP
    SKIP = False
mutate()
@pytest.mark.skipif(SKIP, reason='conditional')
def test_should_fail():
    assert False
""", "static module initialization")

    def test_named_fixture_options_are_protected(self):
        self.rejected("""import pytest
AUTO = False
def mutate():
    global AUTO
    AUTO = True
mutate()
@pytest.fixture(autouse=AUTO)
def broken():
    assert False
def test_ok():
    pass
""", "static module initialization")

    def test_conditional_test_assignments_are_rejected(self):
        self.rejected("""def helper():
    assert False
if True:
    test_other = helper
def test_ok():
    pass
""", "dynamically assigning tests")

    def test_conditional_test_definitions_are_rejected(self):
        self.rejected("if True:\n    def testing():\n        assert False\n", "conditional/nested")

    def test_pytest_default_test_prefix_is_collected(self):
        result = generate("def testing():\n    assert False\n", "test_input.py")
        self.assertEqual(result.cases, ["test_input.py::testing"])
        self.assertIn("testing()", result.source)

    def test_boolean_markers_need_reasons_even_when_false(self):
        for marker in ("skipif", "xfail"):
            for condition in ("True", "False"):
                with self.subTest(marker=marker, condition=condition):
                    self.rejected(f"import pytest\n@pytest.mark.{marker}({condition})\n"
                                  "def test_ok():\n    pass\n", "explicit reason")

    def test_autouse_fixtures_have_pytest_name_order(self):
        self.execute("""import pytest
events: list[str] = []
@pytest.fixture(autouse=True)
def zulu():
    events.append('z')
@pytest.fixture(autouse=True)
def alpha():
    events.append('a')
def test_order():
    assert events == ['a', 'z']
""")

    def test_fixture_parameter_shadowing_is_a_value(self):
        self.execute("""import pytest
@pytest.fixture
def item():
    return [1]
@pytest.fixture
def alias(item):
    return item
def test_alias(item, alias):
    assert item is alias
""")

    def test_direct_fixture_calls_are_rejected(self):
        self.rejected("""import pytest
@pytest.fixture
def item():
    return 1
def test_direct():
    assert item() == 1
""", "only be requested")

    def test_list_argument_names_unpack_single_tuple_rows(self):
        generated, _ = self.execute("""import pytest
@pytest.mark.parametrize(['value'], [(1,), (2,)])
def test_value(value):
    assert value == 1 or value == 2
""")
        self.assertEqual(generated.cases, ["test_input.py::test_value[1]", "test_input.py::test_value[2]"])

    def test_duplicate_and_bytes_parameter_ids(self):
        generated = generate("""import pytest
@pytest.mark.parametrize('value', [1, 1, b'\\n', b'\\xff'])
def test_value(value):
    pass
""", "test_input.py")
        self.assertEqual(generated.cases, ["test_input.py::test_value[1_0]", "test_input.py::test_value[1_1]",
                                           r"test_input.py::test_value[\n]", r"test_input.py::test_value[\xff]"])

    def test_literal_text_cannot_introduce_any_pragma(self):
        generated = generate('"""\n# pystachy: dynamic-any\n"""\ndef test_ok():\n    pass\n', "test_input.py")
        self.assertFalse(generated.source.lstrip().startswith("# pystachy:"))

    def test_shared_mutable_parameters_are_not_copied(self):
        self.execute("""import pytest
VALUES = [1]
@pytest.mark.parametrize('value', [VALUES, VALUES], ids=['first', 'second'])
def test_shared(value):
    assert value is VALUES
    value.append(2)
def test_after():
    assert VALUES == [1, 2, 2]
""")


if __name__ == "__main__":
    unittest.main()
