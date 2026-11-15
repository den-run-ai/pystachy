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

    def test_parameter_sets_emit_the_same_direct_calls(self):
        plain = """import pytest
@pytest.mark.parametrize('value', [1, 2], ids=['first', 'second'])
def test_value(value):
    assert value > 0
"""
        sets = plain.replace("[1, 2], ids=['first', 'second']",
                             "[pytest.param(1, id='first'), pytest.param(2, id='second')]")
        self.assertEqual(generate(plain, "test_input.py"), generate(sets, "test_input.py"))

    def test_empty_literal_hoists_keep_only_their_contextual_annotations(self):
        source = """import pytest
shared: list[int] = []
@pytest.mark.parametrize('value', [[], shared, [1]], ids=['empty', 'shared', 'full'])
def test_value(value: list[int]):
    value.append(2)
"""
        generated, _ = self.execute(source)
        self.assertIn("_pyn_param_0: 'list[int]' = []", generated.source)
        self.assertIn("_pyn_param_1 = shared", generated.source)
        self.assertIn("_pyn_param_2 = [1]", generated.source)
        self.rejected("def test_metadata():\n    assert __annotations__ == {}\n", "module metadata")

    def test_hoisted_annotations_do_not_repeat_python_annotation_evaluation(self):
        self.execute("""import pytest
events: list[str] = []
def annotation():
    events.append('annotation')
    return list[int]
@pytest.mark.parametrize('value', [[]])
def test_value(value: annotation()):
    assert value == []
    assert events == ['annotation']
""")

    def test_explicit_fixture_name_has_no_generated_cost(self):
        source = """import pytest
@pytest.fixture
def value():
    return 3
def test_value(value):
    assert value == 3
"""
        named = source.replace("@pytest.fixture\n", "@pytest.fixture(name='value')\n")
        self.assertEqual(generate(source, "test_input.py"), generate(named, "test_input.py"))

    def test_fixture_alias_calls_implementation_and_rejects_direct_use(self):
        source = """import pytest
@pytest.fixture(name='value')
def make_value():
    return [1]
@pytest.fixture
def same(value):
    return value
def test_value(value, same):
    assert value is same
"""
        generated, _ = self.execute(source)
        self.assertIn("= make_value()", generated.source)
        self.rejected(source + "\ndef test_direct():\n    make_value()\n", "only be requested")

    def test_nested_bindings_cannot_hide_direct_fixture_calls(self):
        prefix = "import pytest\n@pytest.fixture(name='value')\ndef make_value(): return 1\n"
        for shadow in ("def unused():\n        make_value = 0",
                       "class Holder:\n        make_value = 0",
                       "[0 for make_value in [1]]"):
            with self.subTest(shadow=shadow):
                self.rejected(prefix + "def test_direct():\n    " + shadow
                              + "\n    assert make_value() == 1\n", "only be requested")
        self.rejected(prefix + "def test_iterable():\n    [0 for make_value in make_value()]\n",
                      "only be requested")

    def test_genuine_local_fixture_shadows_remain_valid(self):
        self.execute("""import pytest
@pytest.fixture(name='value')
def make_value(): return 0
def test_local():
    def make_value(): return 1
    assert make_value() == 1
def test_import():
    from json import loads as make_value
    assert make_value('1') == 1
def test_comprehension():
    assert [make_value for make_value in [1]] == [1]
def test_walrus():
    assert [(make_value := value) for value in [1]] == [1]
    assert make_value == 1
""")

    def test_evaluated_annotations_cannot_mutate_named_parameter_tables(self):
        prefix = """import pytest
VALUES = [1]
def mutate():
    VALUES[0] = 2
    return int
"""
        for signature in ("def test_value(value: mutate()):", "def test_value(value) -> mutate():"):
            with self.subTest(signature=signature):
                source = prefix + "@pytest.mark.parametrize('value', VALUES)\n" + signature
                source += "\n    assert value == 1\n"
                self.rejected(source, "evaluated annotations")
        # Postponed annotations are strings under the pinned CPython and cannot
        # run mutate() during collection. Keep that supported source unchanged.
        self.execute("from __future__ import annotations\n" + prefix
                     + "@pytest.mark.parametrize('value', VALUES)\n"
                     "def test_value(value: mutate()):\n    assert value == 1\n")

    def test_invalid_or_duplicate_fixture_aliases_are_rejected(self):
        for alias in ("'request'", "'pytest'", "'_pyn_value'", "'class'", "'not an identifier'", "1", "None"):
            with self.subTest(alias=alias):
                self.rejected(f"import pytest\n@pytest.fixture(name={alias})\ndef value(): return 1\n",
                              "non-reserved literal identifier")
        self.rejected("""import pytest
@pytest.fixture(name='same')
def first(): return 1
@pytest.fixture(name='same')
def second(): return 2
def test_value(same): pass
""", "duplicate fixture name")

    def test_parameter_sets_reject_dynamic_or_unknown_metadata(self):
        for row, message in (
            ("pytest.param(1, id=object())", "literal"),
            ("pytest.param(1, id=1)", "literal string"),
            ("pytest.param(1, marks=pytest.mark.usefixtures('first'))", "unsupported marker: usefixtures"),
            ("pytest.param(1, marks=pytest.mark.filterwarnings('error'))", "unsupported marker: filterwarnings"),
            ("pytest.param(1, marks=pytest.mark.slow(object()))", "literal"),
            ("pytest.param(1, marks=[])" + ", pytest.param(2, other=True)", "static marks"),
            ("pytest.param(1, marks=None)", "unsupported marker"),
            ("pytest.param(1, 2)", "row width"),
            ("pytest.param(*[1])", "literal"),
        ):
            with self.subTest(row=row):
                self.rejected("import pytest\n@pytest.mark.parametrize('value', [" + row
                              + "])\ndef test_value(value): pass\n", message)
        self.rejected("""import pytest
VALUES = [pytest.param(1)]
@pytest.mark.parametrize('value', VALUES)
def test_value(value): pass
""", "literal")
        self.rejected("import pytest\ndef test_value():\n    pytest.param(1)\n", "unsupported pytest use")


    def test_new_dialect_keeps_its_rejection_boundaries(self):
        for source, message in (
            ("import pytest\n@pytest.mark.skipif(\"sys.platform == 'win32'\", reason='x')\ndef test_a(): pass\n",
             "string conditions are unsupported"),
            ("import pytest\n@pytest.mark.skipif(pytest.__version__ > '1', reason='x')\ndef test_a(): pass\n",
             "cannot use pytest"),
            ("import sys\nimport pytest\n@pytest.mark.skipif(sys.platform == 'x')\ndef test_a(): pass\n",
             "explicit reason"),
            ("import pytest\nNAMES = ['first']\n@pytest.mark.usefixtures(*NAMES)\ndef test_a(): pass\n",
             "literal"),
            ("import pytest\n@pytest.mark.usefixtures('first', other=1)\ndef test_a(): pass\n",
             "literal fixture names"),
            ("import pytest\n@pytest.mark.filterwarnings('error')\ndef test_a(): pass\n",
             "unsupported marker: filterwarnings"),
            ("import pytest\ndef make(): return 1\n@pytest.mark.slow(make())\ndef test_a(): pass\n",
             "literal"),
            ("import pytest\n@pytest.mark.usefixtures('missing')\ndef test_a(): pass\n",
             "unknown or unsupported fixture: missing"),
            ("def test_a(): pass\nif __name__ == '__main__':\n    pass\nelse:\n    pass\n",
             "module metadata"),
            ("def test_a(): pass\nprint(__name__)\n", "module metadata"),
        ):
            with self.subTest(source=source):
                self.rejected(source, message)

    def test_selection_and_operand_shapes(self):
        source = ("import pytest\n"
                  "def helper(values: list[int]):\n    assert len(values) == 2\n"
                  "class Holder:\n    assert 1 + 1 == 2\n"
                  "def test_a(): pass\n"
                  "@pytest.mark.parametrize('x', [1, 2])\ndef test_p(x):\n    assert x in (1, 2)\n")
        generated = generate(source, "test_input.py", selected=["test_p[2]", "test_a", "test_p"])
        self.assertEqual(generated.cases, ["test_input.py::test_p[2]", "test_input.py::test_a",
                                           "test_input.py::test_p[1]"])
        # Only function bodies take operand temporaries; a class body keeps a plain message.
        self.assertRegex(generated.source, r"\(_pyn_operand_\d+ := len\(values\)\) == 2")
        self.assertIn("assert 1 + 1 == 2, 'test_input.py:5: assert 1 + 1 == 2'", generated.source)
        self.assertNotIn("_pyn_operand", generate(source, "test_input.py", operands=False).source)
        with self.assertRaisesRegex(CollectionError, "not found: test_input.py::test_missing"):
            generate(source, "test_input.py", selected=["test_missing"])


if __name__ == "__main__":
    unittest.main()
