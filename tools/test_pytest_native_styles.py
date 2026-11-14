"""Original-pytest parity for unittest cases, class inheritance, computed tables and layouts."""
import contextlib
import importlib.util
import io
import json
import os
import re
import shlex
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import patch

import pytest_native as runner
from pytest_native_codegen import CollectionError, adapt_helper, generate, generate_conftest
from test_pytest_native import TemporarySuite

NATIVE = os.environ.get("PYSTACHY_PYTEST_NATIVE_COMPILER", "")



UNITTEST = '''
import unittest

import pytest

LOG: list[str] = []


class Base(unittest.TestCase):
    def setUp(self):
        LOG.append("setUp")
        self.value = 3
        self.names = ["a", "b"]
        self.count = 0

    @property
    def label(self) -> str:
        self.count += 1
        return "label"

    def tearDown(self):
        LOG.append("tearDown")

    def test_zeta(self):
        self.assertEqual(self.value, 3)

    def test_alpha(self):
        self.assertTrue(self.names)
        self.assertIn("a", self.names)


class Derived(Base):
    def test_middle(self):
        self.assertIn(self.value, [3])
        self.assertIsInstance(self.value, int)
        self.assertNotIsInstance(self.names, int)

    def test_fail(self):
        self.assertEqual(1, 2)

    def test_error(self):
        raise KeyError("k")

    def test_skip(self):
        self.skipTest("later")

    @unittest.skip("decorated")
    def test_skip_decorated(self):
        raise RuntimeError("never")

    @unittest.skipIf(True, "cond")
    def test_skip_if(self):
        raise RuntimeError("never")

    @unittest.skipIf(len(LOG) > 1000, "runtime cond")
    def test_skip_if_runtime(self):
        self.assertLess(1, 2)

    @unittest.skipUnless(True, "cond")
    def test_skip_unless(self):
        pass

    @unittest.expectedFailure
    def test_expected(self):
        self.assertEqual(1, 2)

    @unittest.expectedFailure
    def test_unexpected(self):
        pass

    @unittest.expectedFailure
    def test_expected_in_subtest(self):
        # unittest stops at the first failing subtest: the failure it expects.
        for i in range(3):
            with self.subTest(i=i):
                self.assertLess(i, 1)
        LOG.append("after expected subtests")

    @unittest.expectedFailure
    def test_unexpected_in_subtests(self):
        for i in range(2):
            with self.subTest(i=i):
                self.assertLess(i, 2)

    def test_sub_arguments_run(self):
        # A parameter is evaluated where the block is entered: a property runs.
        with self.subTest(x=self.label):
            self.assertEqual(self.count, 1)
        with self.subTest(self.label, y=self.names[0]):
            self.assertEqual(self.count, 2)

    def test_sub_nested(self):
        # A subtest whose nested subtest failed reports no success of its own.
        with self.subTest(outer=1):
            with self.subTest(inner=1):
                self.assertEqual(1, 2)
            LOG.append("after nested failure")
        with self.subTest(outer=2):
            with self.subTest(inner=2):
                self.assertEqual(1, 1)

    def test_raises_fails_as_an_assertion(self):
        with self.assertRaises(AssertionError):
            with self.assertRaises(ValueError):
                pass
        with self.assertRaises(AssertionError):
            self.assertRaises(ValueError, int, "3")
        with self.assertRaises(AssertionError):
            with self.assertRaisesRegex(ValueError, "never"):
                int("x")

    def test_sub_pass(self):
        for i in range(3):
            with self.subTest(i=i):
                self.assertLess(i, 3)

    def test_sub_fail(self):
        for i in range(3):
            with self.subTest(i=i):
                self.assertLess(i, 1)
        LOG.append("after subtests")

    def test_pytest_skip(self):
        pytest.skip("pytest skip in unittest")

    def test_pytest_fail(self):
        pytest.fail("pytest fail")

    def test_raises(self):
        with self.assertRaises(ValueError) as cm:
            int("x")
        self.assertIn("invalid", str(cm.exception))
        self.assertRaises(ValueError, int, "y")
        with self.assertRaisesRegex(ValueError, "invalid"):
            int("z")
        with self.assertRaises((KeyError, ValueError)):
            int("w")

    def test_numbers(self):
        self.assertAlmostEqual(0.1 + 0.2, 0.3)
        self.assertAlmostEqual(1.0, 1.05, delta=0.1)
        self.assertNotAlmostEqual(1.0, 2.0)
        self.assertGreater(2, 1)
        self.assertLessEqual(1, 1)
        self.assertNotEqual("a", "b")
        self.assertIsNone(None)
        empty: list[int] = []
        self.assertFalse(empty)
        self.assertCountEqual([1, 2, 2], [2, 1, 2])
        self.assertSequenceEqual([1, 2], [1, 2])
        self.assertDictEqual({"a": 1}, {"a": 1})
        self.assertRegex("hello", "ell")


class TearDownFails(unittest.TestCase):
    def tearDown(self):
        raise RuntimeError("teardown")

    def test_pass(self):
        pass

    def test_fail(self):
        self.fail("body")

    def test_skip(self):
        self.skipTest("s")


class SetUpFails(unittest.TestCase):
    def setUp(self):
        raise RuntimeError("setup")

    def tearDown(self):
        LOG.append("tearDown after failed setUp")

    def test_one(self):
        pass


class SetUpSkips(unittest.TestCase):
    def setUp(self):
        raise unittest.SkipTest("setup skip")

    def test_one(self):
        pass


@unittest.skip("whole class")
class SkippedClass(unittest.TestCase):
    def test_one(self):
        raise RuntimeError("never")


class NotNamedTest(unittest.TestCase):
    def test_b(self):
        pass

    def test_a(self):
        pass

    def helper(self):
        pass


@pytest.fixture(autouse=True)
def auto():
    LOG.append("auto+")
    yield
    LOG.append("auto-")


class Checks(unittest.TestCase):
    def check(self, value: int) -> None:
        with self.subTest(value=value):
            self.assertEqual(value, 1)


def test_subtest_outside_a_case_does_not_hide_its_failure():
    # No case is running: unittest lets the failure through, and so must the runner.
    Checks().check(2)


def test_plain_last():
    assert "after subtests" in LOG
    assert "after expected subtests" not in LOG
    assert "after nested failure" in LOG
    assert "tearDown after failed setUp" not in LOG
    assert LOG[:4] == ["auto+", "setUp", "tearDown", "auto-"]
'''


TABLES = '''
import itertools
import os

import pytest

SIZES = [1, 2, 3]
NAMES = ("a", "b")
PAIRS = {"one": 1, "two": 2}
DOUBLED = [n * 2 for n in SIZES]
GRID = list(itertools.product(SIZES[:2], NAMES))
LABELS = [f"case{n}" for n in range(3)]
MUTATED = [1, 2]
HERE = os.path.dirname(__file__)


class Point:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


def make(n: int) -> Point:
    return Point(n, n + 1)


POINTS = [Point(1, 2), Point(3, 4)]


def change():
    MUTATED[1] = 2


@pytest.mark.parametrize("n", range(3))
def test_range(n):
    assert n in (0, 1, 2)


@pytest.mark.parametrize("n", DOUBLED)
def test_named_comprehension(n):
    assert n % 2 == 0


@pytest.mark.parametrize(("n", "name"), GRID)
def test_product(n, name):
    assert n in SIZES and name in NAMES


@pytest.mark.parametrize("key, value", sorted(PAIRS.items()))
def test_items(key, value):
    assert PAIRS[key] == value


@pytest.mark.parametrize("key", PAIRS)
def test_dict_keys(key):
    assert key in ("one", "two")


@pytest.mark.parametrize("point", [Point(1, 2), make(5)])
def test_objects(point):
    assert point.y == point.x + 1


@pytest.mark.parametrize("point", POINTS)
def test_named_objects(point):
    assert point.y == point.x + 1


@pytest.mark.parametrize("point, total", [(make(n), n * 2 + 1) for n in SIZES])
def test_comprehension_of_objects(point, total):
    assert point.x + point.y == total


@pytest.mark.parametrize("kind", [ValueError, KeyError, make])
def test_named_values(kind):
    assert kind is not None


@pytest.mark.parametrize("n", SIZES + [10, 20], ids=LABELS + ["ten", None])
def test_joined(n):
    assert n > 0


@pytest.mark.parametrize("n", [1, 2, 3], ids=[None, "two", 3])
def test_mixed_ids(n):
    assert n > 0


@pytest.mark.parametrize("value", MUTATED)
def test_reads_the_table_after_import(value):
    assert value in (1, 2)


change()


@pytest.mark.parametrize("n", [x for x in range(10) if x % 3 == 0])
def test_filtered(n):
    assert n % 3 == 0


@pytest.mark.parametrize("text", ["a" * 3, "x" + "y", 2 ** 4, -1, 1.5 * 2])
def test_folded(text):
    assert text is not None


def test_module_metadata():
    assert __name__ == "test_tables"
    assert os.path.basename(__file__) == "test_tables.py"
    assert os.path.isdir(HERE)
'''


MARKS = '''
import sys
from typing import Callable

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.skipif(sys.platform == "nonesuch", reason="never")]

LOG: list[str] = []


@pytest.fixture
def noted():
    LOG.append("noted")


class Problem(Exception):
    def __init__(self, code: int) -> None:
        super().__init__("problem " + str(code))
        self.code = code


def explode(code: int, scale: int = 1) -> None:
    raise Problem(code * scale)


def quiet() -> None:
    pass


class TestMarked:
    pytestmark = pytest.mark.usefixtures("noted")

    def test_fixture_ran(self):
        assert LOG == ["noted"]


class TestSkippedByAttribute:
    pytestmark = [pytest.mark.skip(reason="class attribute")]

    def test_never(self):
        assert False


def test_callable_raises():
    pytest.raises(Problem, explode, 3)
    pytest.raises(Problem, explode, 3, scale=2)
    info = pytest.raises(Problem, explode, 4)
    assert "problem 4" in str(info.value)


def test_callable_raises_misses():
    pytest.raises(Problem, quiet)


def test_callable_arguments_run_before_the_call():
    def argument() -> int:
        raise Problem(1)

    # pytest evaluates the arguments first: their exception is the test's own.
    pytest.raises(Problem, explode, argument())


def explode_one(code: int) -> None:
    raise Problem(code)


def quiet_one(code: int) -> None:
    pass


class Switch:
    def __init__(self) -> None:
        self.action: Callable[[int], None] = explode_one
        self.code = 3

    @property
    def broken(self) -> Callable[[int], None]:
        raise Problem(7)

    def flip(self) -> int:
        self.action = quiet_one
        self.code = 5
        return 1


def test_callable_lookup_runs_before_the_context():
    switch = Switch()
    # The property raises where pytest evaluates raises()'s arguments: the test's own.
    pytest.raises(Problem, switch.broken, 1)


def test_callable_is_read_before_its_arguments():
    switch = Switch()
    # The field is read before flip() replaces it, so the call raises.
    pytest.raises(Problem, switch.action, switch.flip())
    again = Switch()
    # An argument is read before a later one's call changes it.
    info = pytest.raises(Problem, explode, again.code, again.flip())
    assert "problem 3" in str(info.value)
'''


INHERIT = '''
import pytest

LOG: list[str] = []


@pytest.fixture
def noted():
    LOG.append("noted")


class Shared:
    limit = 10

    @pytest.fixture
    def base(self) -> int:
        return 5

    def test_shared(self, base):
        assert base < self.limit

    def test_overridden(self):
        assert False

    def test_inherited_as_is(self):
        assert self.limit >= 10


@pytest.mark.usefixtures("noted")
class TestFirst(Shared):
    @pytest.mark.parametrize("scale", [1, 2])
    def test_own(self, base, scale):
        assert base * scale <= self.limit
        assert LOG[-1] == "noted"

    def test_overridden(self):
        assert self.limit


class TestSecond(TestFirst):
    limit = 100

    @pytest.fixture
    def base(self) -> int:
        return 50

    def test_last(self, base):
        assert base == 50


class Helper:
    def test_not_collected(self):
        assert False
'''


WARNS = '''
import unittest
import warnings

import pytest


def old(value: int) -> int:
    warnings.warn("old thing " + str(value), DeprecationWarning)
    return value


def loud() -> None:
    warnings.warn("careful", UserWarning)


def quiet() -> int:
    return 1


def test_warns():
    with pytest.warns(DeprecationWarning):
        assert old(2) == 2
    with pytest.warns(DeprecationWarning, match="thing 3") as record:
        old(3)
    assert len(record) == 1
    assert "old thing 3" in str(record[0].message)
    with pytest.warns((UserWarning, DeprecationWarning)):
        loud()
    with pytest.warns():
        loud()
    with pytest.deprecated_call():
        old(1)


def test_did_not_warn():
    with pytest.warns(UserWarning):
        quiet()


def test_wrong_class():
    with pytest.warns(UserWarning):
        old(1)


def test_match_misses():
    with pytest.warns(DeprecationWarning, match="nothing"):
        old(1)


def test_exception_propagates():
    with pytest.raises(ZeroDivisionError):
        with pytest.warns(UserWarning):
            quiet() // 0


class Case(unittest.TestCase):
    def test_assert_warns(self):
        with self.assertWarns(DeprecationWarning):
            old(1)
        with self.assertWarnsRegex(UserWarning, "care"):
            loud()

    def test_assert_warns_fails(self):
        with self.assertWarns(UserWarning):
            quiet()
'''


XUNIT = '''
import pytest

LOG: list[str] = []


@pytest.fixture(autouse=True)
def module_auto():
    LOG.append("module+")
    yield
    LOG.append("module-")


@pytest.fixture(scope="module")
def wide():
    LOG.append("wide+")
    yield 1
    LOG.append("wide-")


class TestHooks:
    def setup_method(self, method):
        LOG.append("setup_method")
        self.items = [1, 2]
        self.total = 0

    def teardown_method(self, method=None):
        LOG.append("teardown_method")

    @pytest.fixture(autouse=True)
    def class_auto(self):
        LOG.append("class+ " + str(len(self.items)))
        yield
        LOG.append("class-")

    def test_order(self, wide):
        assert LOG == ["wide+", "module+", "setup_method", "class+ 2"]
        self.total = sum(self.items)
        assert self.total == 3

    def test_fresh_object(self):
        assert self.total == 0
        assert LOG[-6:] == ["class-", "teardown_method", "module-", "module+", "setup_method", "class+ 2"]


class TestDerived(TestHooks):
    def setup_method(self, method):
        super().setup_method(method)
        self.extra = "x"

    def test_inherited_hooks(self):
        assert self.extra == "x" and self.items == [1, 2]


class TestSetupFails:
    def setup_method(self):
        raise RuntimeError("no setup")

    def teardown_method(self):
        LOG.append("never")

    def test_never_runs(self):
        assert False


class TestTeardownFails:
    def teardown_method(self):
        raise RuntimeError("no teardown")

    def test_passes(self):
        pass

    def test_fails(self):
        assert False


class TestNoseNames:
    def setup(self):
        LOG.append("nose setup")

    def teardown(self):
        LOG.append("nose teardown")

    def test_plain_methods(self):
        assert "never" not in LOG
        assert "nose setup" not in LOG
'''


HINTS = '''
from pathlib import Path

import pytest

TOKENS = {"b": [2], "a": [1]}


@pytest.fixture(params=sorted(TOKENS))
def token(request: pytest.FixtureRequest) -> list[int]:
    return TOKENS[request.param]


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("PYN_HOME", str(tmp_path))
    return tmp_path


def test_annotated_fixtures(token: list[int], home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    assert os.environ["PYN_HOME"] == str(home)
    assert token in ([1], [2])
    monkeypatch.setenv("PYN_OTHER", "1")
'''


PACKAGES = {
    'conftest.py': 'import pytest\n\nLOG: list[str] = []\n\n\n@pytest.fixture(autouse=True)\ndef outer_auto():\n    LOG.append("outer+")\n    yield\n    LOG.append("outer-")\n\n\n@pytest.fixture\ndef size() -> int:\n    return 2\n\n\n@pytest.fixture(scope="session")\ndef shared_log() -> list[str]:\n    return LOG\n',
    'extra/flat_helper.py': 'def where() -> str:\n    return __file__\n',
    'extra/test_flat.py': 'import flat_helper\n\n\ndef test_outer_conftest_only(size, shared_log):\n    assert size == 2\n    assert shared_log[-1] == "outer+"\n    assert flat_helper.where().endswith("flat_helper.py")\n',
    'shapes/__init__.py': 'def area(width: int, height: int) -> int:\n    return width * height\n',
    'tests/__init__.py': '',
    'tests/conftest.py': 'import pytest\n\n\n@pytest.fixture(autouse=True)\ndef inner_auto(shared_log):\n    shared_log.append("inner+")\n    yield\n    shared_log.append("inner-")\n\n\n@pytest.fixture\ndef size() -> int:\n    return 5\n\n\n@pytest.fixture\ndef doubled(size) -> int:\n    return size * 2\n',
    'tests/data/sizes.txt': '3\n4\n',
    'tests/helpers.py': 'import os\n\nDATA = os.path.join(os.path.dirname(__file__), "data", "sizes.txt")\n\n\ndef read_sizes() -> list[int]:\n    with open(DATA) as handle:\n        return [int(line) for line in handle.read().split()]\n',
    'tests/test_area.py': 'from shapes import area\n\nfrom . import helpers\nfrom .helpers import read_sizes\n\n\ndef test_data_file():\n    assert read_sizes() == [3, 4]\n    assert helpers.DATA.endswith("sizes.txt")\n\n\ndef test_nearer_conftest_wins(size, doubled, shared_log):\n    assert area(size, doubled) == 50\n    assert shared_log[-2:] == ["outer+", "inner+"]\n\n\ndef test_module_name():\n    assert __name__ == "tests.test_area"\n',
    'tests/unit/__init__.py': '',
    'tests/unit/test_deep.py': 'import pytest\n\nfrom .. import helpers\nfrom ..helpers import read_sizes\nfrom ..test_area import area\n\n\n@pytest.fixture\ndef size() -> int:\n    return 7\n\n\ndef test_module_fixture_overrides_conftest(size, doubled):\n    assert (size, doubled) == (7, 14)\n\n\ndef test_parent_package():\n    assert sum(read_sizes()) == 7\n    assert area(1, 2) == 2\n    assert helpers.read_sizes()[0] == 3\n',
}


IMPORTED = {
    'flat/base.py': 'import unittest\n\n\nclass Base(unittest.TestCase):\n    def setUp(self):\n        self.items = [1, 2]\n\n    def check(self, total: int) -> None:\n        self.assertEqual(sum(self.items), total)\n',
    'flat/test_flat_unit.py': 'from base import Base\n\n\nclass FlatCase(Base):\n    def test_total(self):\n        self.check(3)\n\n    def test_fails(self):\n        self.check(4)\n',
    'tests/__init__.py': 'import unittest\n\n\nclass CalTestCase(unittest.TestCase):\n    def setUp(self):\n        self.epoch = 100\n\n    def assertAllPositive(self, seq):\n        for item in seq:\n            self.assertGreater(item, 0)\n\n    def reflexive(self, value: int) -> int:\n        return value\n\n\nclass SharedCases(CalTestCase):\n    def test_shared_one(self):\n        self.assertEqual(self.reflexive(self.epoch), 100)\n\n    def test_shared_two(self):\n        self.assertGreater(self.epoch, 1)\n',
    'tests/test_coptic.py': 'from . import CalTestCase, SharedCases\n\n\nclass TestCoptic(CalTestCase):\n    def setUp(self):\n        super().setUp()\n        self.leap = 1839\n\n    def test_epoch(self):\n        self.assertEqual(self.epoch + self.leap, 1939)\n\n    def test_sequence(self):\n        self.assertAllPositive([1, 2, 3])\n\n\nclass TestMore(SharedCases):\n    def test_own(self):\n        self.assertEqual(self.epoch, 100)\n',
}


RESOLVED = {
    # A base class in the package under test, found from --root, and one reached as module.Class.
    'lib/__init__.py': '',
    'lib/testing.py': 'import unittest\n\n\nclass LibCase(unittest.TestCase):\n    def setUp(self):\n        self.base = 10\n\n    def assertDouble(self, value: int, expected: int) -> None:\n        self.assertEqual(value * 2, expected)\n\n\nclass TestHelperWithInit:\n    def __init__(self, value: int) -> None:\n        self.value = value\n\n\nclass TestKit:\n    def test_kit(self):\n        assert True\n\n\ndef TestFactory() -> int:\n    return 3\n',
    'tests/__init__.py': '',
    'tests/shared.py': 'class Checks:\n    def total(self, a: int, b: int) -> int:\n        return a + b\n\n    def test_inherited(self):\n        assert self.total(1, 2) == 3\n',
    'tests/test_resolved.py': 'from lib.testing import LibCase, TestFactory, TestHelperWithInit, TestKit\nfrom . import shared\n\n\nclass LibraryCase(LibCase):\n    def test_double(self):\n        self.assertDouble(self.base, 20)\n\n    def test_fails(self):\n        self.assertDouble(self.base, 21)\n\n\nclass TestShared(shared.Checks):\n    def test_own(self):\n        assert self.total(2, 2) == 4\n\n\ndef test_inert_names():\n    assert TestHelperWithInit(2).value == 2\n    assert TestFactory() == 3\n',
}


# tmp_path_factory, tmpdir, caplog and the monkeypatch calls the generator writes out.
FIXTURES = {
    'settings.py': 'LIMIT = 5\nNAMES: dict[str, int] = {"a": 1}\n\n\ndef limit() -> int:\n    return LIMIT\n\n\nclass Config:\n    def __init__(self) -> None:\n        self.depth = 1\n        self.label = "x"\n',
    'test_fixtures.py': 'import logging\nimport os\n\nimport pytest\n\nimport settings\n\nLOG = logging.getLogger("pkg.sub")\nTABLE = {"k": 1, "j": 2}\n\n\ndef test_setattr_object(monkeypatch):\n    config = settings.Config()\n    monkeypatch.setattr(config, "depth", 7)\n    monkeypatch.setattr(config, "label", "patched")\n    assert config.depth == 7 and config.label == "patched"\n    monkeypatch.undo()\n    assert config.depth == 1 and config.label == "x"\n\n\ndef test_setattr_module(monkeypatch):\n    monkeypatch.setattr(settings, "LIMIT", 50)\n    assert settings.limit() == 50\n\n\ndef test_module_restored():\n    assert settings.limit() == 5\n\n\ndef test_setitem_and_delitem(monkeypatch):\n    for key in ["k", "new"]:\n        monkeypatch.setitem(TABLE, key, 10)\n    monkeypatch.delitem(TABLE, "j")\n    monkeypatch.delitem(TABLE, "absent", raising=False)\n    assert TABLE == {"k": 10, "new": 10}\n    with pytest.raises(KeyError):\n        monkeypatch.delitem(TABLE, "absent")\n    monkeypatch.setitem(settings.NAMES, "b", 2)\n    assert settings.NAMES == {"a": 1, "b": 2}\n\n\ndef test_items_restored():\n    assert TABLE == {"k": 1, "j": 2}\n    assert settings.NAMES == {"a": 1}\n\n\ndef test_context(monkeypatch):\n    with monkeypatch.context() as m:\n        m.setattr(settings, "LIMIT", 9)\n        m.setenv("PYN_CONTEXT", "1")\n        assert settings.limit() == 9\n    assert settings.limit() == 5\n    assert "PYN_CONTEXT" not in os.environ\n\n\ndef test_caplog(caplog):\n    LOG.warning("first %s", "one")\n    LOG.info("not recorded")\n    assert caplog.messages == ["first one"]\n    assert caplog.record_tuples == [("pkg.sub", logging.WARNING, "first one")]\n    assert "first one" in caplog.text\n    caplog.clear()\n    caplog.set_level(logging.INFO)\n    LOG.info("second")\n    assert [record.levelname for record in caplog.records] == ["INFO"]\n    with caplog.at_level(logging.DEBUG, logger="pkg"):\n        LOG.debug("third")\n    LOG.debug("fourth")\n    assert caplog.messages == ["second", "third"]\n\n\ndef test_caplog_levels_restored(caplog):\n    LOG.info("dropped")\n    assert caplog.records == []\n\n\n@pytest.fixture(scope="session")\ndef shared_dir(tmp_path_factory):\n    directory = tmp_path_factory.mktemp("shared")\n    (directory / "data.txt").write_text("payload")\n    return directory\n\n\ndef test_factory(shared_dir, tmp_path_factory):\n    assert (shared_dir / "data.txt").read_text() == "payload"\n    assert shared_dir.name == "shared0"\n    other = tmp_path_factory.mktemp("shared")\n    assert other.name == "shared1"\n    plain = tmp_path_factory.mktemp("plain", numbered=False)\n    assert plain.name == "plain" and plain.parent == tmp_path_factory.getbasetemp()\n\n\ndef test_tmpdir(tmpdir):\n    target = tmpdir.join("sub", "file.txt")\n    target.ensure()\n    target.write("text")\n    assert target.read() == "text"\n    assert target.check() and target.isfile() and target.basename == "file.txt"\n    assert [item.basename for item in tmpdir.listdir()] == ["sub"]\n    made = tmpdir.mkdir("made")\n    assert made.isdir() and os.path.isdir(str(made))\n    assert (tmpdir / "made") == made\n',
}


# capsys, capfd and monkeypatch.chdir: natively these need os.dup, os.dup2, os.close and os.chdir.
CAPTURE = {
    'test_capture.py': 'import os\nimport sys\n\nimport pytest\n\n\ndef test_capsys(capsys):\n    print("hello")\n    sys.stderr.write("problem\\n")\n    captured = capsys.readouterr()\n    assert captured.out == "hello\\n"\n    assert captured.err == "problem\\n"\n    print("again", end="")\n    out, err = capsys.readouterr()\n    assert (out, err) == ("again", "")\n    assert capsys.readouterr().out == ""\n\n\ndef test_capfd(capfd):\n    print("first")\n    sys.stdout.write("second\\n")\n    out, err = capfd.readouterr()\n    assert out == "first\\nsecond\\n" and err == ""\n    with capfd.disabled():\n        pass\n    print("after")\n    assert capfd.readouterr().out == "after\\n"\n\n\n@pytest.fixture\ndef announced(capsys):\n    print("setup output")\n    return 1\n\n\ndef test_fixture_output_is_captured(announced, capsys):\n    assert capsys.readouterr().out == "setup output\\n"\n    assert announced == 1\n\n\ndef test_chdir(monkeypatch, tmp_path):\n    start = os.getcwd()\n    monkeypatch.chdir(tmp_path)\n    assert os.path.realpath(os.getcwd()) == os.path.realpath(str(tmp_path))\n    inner = tmp_path / "inner"\n    inner.mkdir()\n    monkeypatch.chdir(str(inner))\n    assert os.path.basename(os.getcwd()) == "inner"\n    monkeypatch.undo()\n    assert os.getcwd() == start\n\n\ndef test_cwd_restored(monkeypatch, tmp_path):\n    monkeypatch.chdir(tmp_path)\n\n\ndef test_cwd_is_back():\n    assert os.path.exists("test_capture.py")\n',
}
DESCRIPTORS = "import os\nos.close(os.dup2(os.dup(1), 9))\nos.chdir('.')\n"


CONFIGURED = {
    'pyproject.toml': '[project]\nname = "sample"\n\n[tool.pytest.ini_options]\nminversion = "8.0"\ntestpaths = ["tests"]\naddopts = "-ra --strict-markers --tb=short -W error::DeprecationWarning"\nxfail_strict = true\npythonpath = ["src"]\nmarkers = ["slow: takes a while"]\nfilterwarnings = ["ignore:harmless:UserWarning"]\nlog_cli_level = "INFO"\n',
    'src/lib/__init__.py': 'import warnings\n\n\ndef old() -> int:\n    warnings.warn("old", DeprecationWarning)\n    return 1\n\n\ndef noisy() -> int:\n    warnings.warn("harmless noise", UserWarning)\n    return 2\n',
    'tests/test_config.py': 'import pytest\n\nimport lib\n\n\n@pytest.mark.slow\ndef test_imports_from_pythonpath():\n    assert lib.noisy() == 2\n\n\n@pytest.mark.xfail(reason="strict by configuration")\ndef test_strict_xpass_fails():\n    assert True\n\n\n@pytest.mark.xfail(reason="still expected")\ndef test_xfail():\n    assert False\n\n\ndef test_deprecation_is_an_error():\n    lib.old()\n\n\ndef test_expected_warning():\n    with pytest.warns(DeprecationWarning):\n        lib.old()\n',
}


# The configured project again, with a conftest.py whose session and collection hooks
# pytest runs and the program leaves out, and tests named by marks and expressions.
HOOKS = '''
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

    from _pytest.fixtures import SubRequest


def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "net: needs the network")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(pytest.mark.net)


def pytest_report_header(config):
    return "sample " + str(eval("1 + 1"))


@pytest.fixture
def numbers(request: SubRequest) -> list[int]:
    return [1, 2, 3]


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("PYN_HOME", "/tmp/pyn")
    yield "/tmp/pyn"
'''

SELECTED = '''
import sys

import pytest

import lib

slow = pytest.mark.slow
quiet = pytest.mark.filterwarnings("ignore::DeprecationWarning")
posix = pytest.mark.skipif(sys.platform == "win32", reason="posix only")
cases = pytest.mark.parametrize("value", [1, 2])
mark = pytest.mark


@slow
@quiet
def test_alias_quiets_the_configured_error():
    assert lib.old() == 1


@mark.net
def test_marker_registered_by_a_hook(numbers):
    assert sum(numbers) == 6


@cases
def test_alias_table(value, home):
    assert value > 0 and home != ""


@posix
def test_alias_condition():
    assert True


@pytest.mark.filterwarnings("error::UserWarning")
def test_mark_overrides_the_configured_ignore():
    with pytest.raises(UserWarning):
        lib.noisy()


@pytest.mark.filterwarnings("error::UserWarning")
@pytest.mark.filterwarnings("ignore:harmless noise")
def test_the_outer_mark_wins():
    with pytest.raises(UserWarning):
        lib.noisy()


def test_recwarn(recwarn):
    assert lib.old() == 1
    assert len(recwarn) == 1
    assert recwarn.pop(DeprecationWarning).category is DeprecationWarning
    assert len(recwarn.list) == 0
'''

# Tests the collector rejects, each for one form, among tests it collects.
UNCOLLECTED = """
import os
from unittest import mock

import pytest


def values():
    return [1, 2]


class MixinA:
    def test_a(self):
        assert True


class MixinB:
    def test_b(self):
        assert True


def test_plain():
    assert values() == [1, 2]


@pytest.mark.parametrize("value", values())
def test_table(value):
    assert value


@mock.patch("os.getcwd")
def test_patched(getcwd):
    assert getcwd is os.getcwd


def test_dotted(monkeypatch):
    monkeypatch.setattr("os.sep", "!")
    assert os.sep == "!"


class TestBoth(MixinA, MixinB):
    def test_own(self):
        assert True


class TestDerived(TestBoth):
    def test_more(self):
        assert True


class TestGroup:
    def test_kept(self):
        assert True

    @pytest.mark.parametrize("value", values())
    def test_method_table(self, value):
        assert value


def test_last():
    assert True
"""

# Tests a native compiler rejects: each calls typed code in a way only CPython can run.
UNCOMPILED = """
import dis

import pytest


def scale(value: int, factor: int = 2) -> int:
    if not isinstance(value, int):
        raise TypeError("value must be an int")
    return value * factor


def twice(value):
    return scale(value)


def test_first():
    assert scale(2) == 4


def test_wrong_type():
    with pytest.raises(TypeError):
        scale("two")


@pytest.mark.parametrize("value", [1, "one", 3])
def test_values(value):
    if isinstance(value, int):
        assert twice(value) == 2 * value
    else:
        with pytest.raises(TypeError):
            twice(value)


class TestGroup:
    def test_fine(self):
        assert scale(3, 3) == 9

    def test_missing_argument(self):
        with pytest.raises(TypeError):
            scale()

    def test_last(self):
        assert scale(0) == 0


def test_end():
    assert twice(5) == 10


def test_bytecode():
    assert "RETURN_VALUE" in dis.opmap
"""
UNCOMPILED_CASES = {"test_wrong_type", "test_values[1]", "test_values[one]", "test_values[3]",
                    "TestGroup::test_missing_argument", "test_bytecode"}

# A stand-in for the compiler that rejects a program whose test modules have a line with
# REJECTED, naming the first as the compiler names a line, and otherwise runs it in CPython.
# An import of such a name is a module or a name it lacks; a use of one that no import of the
# file binds is an undefined name.
REJECTING_COMPILER = """
import pathlib, re, runpy, sys
assert sys.argv[1] == "run"
directory = pathlib.Path(sys.argv[2]).parent
for file in sorted([*directory.glob("conftest.py"), *directory.glob("test_*.py")]):
    lines = file.read_text().splitlines()
    imported = {name for line in lines if re.match(r"(import|from) ", line) for name in re.findall(r"REJECTED_\\w+", line)}
    for number, line in enumerate(lines, 1):
        found = re.search(r"REJECTED(_\\w+)?", line)
        if not found:
            continue
        if line.startswith("import "):
            reason = "module 'missing' is not supported"
        elif line.startswith("from "):
            reason = f"cannot import name '{found.group(0)}' from 'values'"
        elif found.group(1) and found.group(0) not in imported:
            reason = f"name '{found.group(0)}' is not defined"
        else:
            reason = f"rejected (compiling f() for the call at {file}:{number})"
        print(f"{file}:{number}: error: {reason}", file=sys.stderr)
        sys.exit(1)
sys.argv = sys.argv[2:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""

# Imports the stand-in rejects: a module, and one name of a from-import's three.
UNIMPORTED = """
from __future__ import annotations

import json as REJECTED_json
import os.path
from values import (
    KEPT,
    REJECTED_name,
    other as renamed,
)


def test_uses_the_module():
    assert REJECTED_json.dumps([1]) == "[1]"


def test_uses_the_name():
    assert REJECTED_name == 2


def test_uses_the_others():
    assert KEPT + renamed == 4 and os.path.basename("a/b") == "b"


class TestGroup:
    def test_method_uses_the_module(self):
        assert REJECTED_json.loads("2") == 2

    def test_kept(self):
        assert KEPT == 1
"""

REJECTED = """
import pytest

LOG: list[str] = []


def helper():
    return 1


def test_first():
    LOG.append("first")
    assert helper() == 1


@pytest.mark.parametrize(
    "value",
    [1, 2],
)
def test_marked(value):
    REJECTED = value
    assert REJECTED


class TestGroup:
    def setup_method(self):
        LOG.append("setup")

    def test_kept(self):
        assert LOG[-1] == "setup"

    @pytest.mark.skip(reason="never")
    def test_method(self):
        REJECTED = 1

    def test_also_kept(self):
        assert helper() == 1


class TestWhole:
    REJECTED = 1

    def test_one(self):
        assert self.REJECTED

    def test_two(self):
        assert True


def test_last():
    assert LOG[0] == "first"
"""

SUITES = {
    "unit": (UNITTEST, "test-failed"),
    "tables": (TABLES, "passed"),
    "marks": (MARKS, "test-failed"),
    "inherit": (INHERIT, "passed"),
    "warns": (WARNS, "test-failed"),
    "xunit": (XUNIT, "test-failed"),
    "hints": (HINTS, "passed"),
}


@unittest.skipUnless(importlib.util.find_spec("pytest"), "real pytest required for independent oracle")
class StyleParity(TemporarySuite):
    def files(self, files, configured=False):
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return runner.discover([self.root], self.root, configured)

    def run_paths(self, paths, mode):
        results = runner.run_suite(paths, self.root, self.work / mode, mode, shlex.split(NATIVE), sys.executable, 300)
        expected = runner.oracle(paths, self.root, self.work / "oracle", sys.executable, 120)
        self.assertEqual(runner.compare(results, expected), [], results[0].error + results[0].stderr + json.dumps(
            runner.outcome_differences(results, expected), indent=2))
        return results, expected

    def suites(self, mode):
        """Every suite as one program, as one pytest session runs them."""
        paths = sorted(self.source(source, f"test_{name}.py") for name, (source, _) in SUITES.items())
        results, expected = self.run_paths(paths, mode)
        self.assertEqual({result.path: result.state for result in results},
                         {f"test_{name}.py": state for name, (_, state) in SUITES.items()})
        return results, expected

    def outcomes(self, results):
        return {(event["nodeid"], event["phase"]): event["outcome"] for result in results
                for event in result.events if event["phase"] != "subtest"}

    def test_suites_match_pytest(self):
        results, expected = self.suites("python")
        cases = expected["cases"]
        self.assertEqual(len(cases), 115)
        outcomes = self.outcomes(results)
        # unittest sorts a case's methods, inherited ones too, and runs setUp, the test
        # and tearDown in the call phase; a second failure is the teardown's.
        derived = [case.split("::")[2] for case in cases if case.startswith("test_unit.py::Derived::")]
        self.assertEqual(derived, sorted(derived))
        self.assertIn("test_alpha", derived)
        self.assertEqual(outcomes["test_unit.py::Derived::test_expected", "call"], "xfailed")
        self.assertEqual(outcomes["test_unit.py::Derived::test_unexpected", "call"], "failed")
        self.assertEqual(outcomes["test_unit.py::Derived::test_skip_decorated", "call"], "skipped")
        self.assertEqual(outcomes["test_unit.py::Derived::test_skip_if_runtime", "call"], "passed")
        self.assertEqual(outcomes["test_unit.py::SkippedClass::test_one", "setup"], "skipped")
        self.assertEqual(outcomes["test_unit.py::SetUpFails::test_one", "call"], "failed")
        self.assertEqual(outcomes["test_unit.py::TearDownFails::test_pass", "call"], "failed")
        self.assertEqual(outcomes["test_unit.py::TearDownFails::test_pass", "teardown"], "passed")
        self.assertEqual(outcomes["test_unit.py::TearDownFails::test_fail", "teardown"], "error")
        self.assertEqual(outcomes["test_unit.py::TearDownFails::test_skip", "call"], "skipped")
        subtests = [(event["nodeid"].rsplit("::", 1)[1], event["outcome"]) for result in results
                    for event in result.events if event["phase"] == "subtest"]
        self.assertEqual(subtests, [("test_expected_in_subtest", "passed"), *[("test_sub_arguments_run", "passed")] * 2,
                                    ("test_sub_fail", "passed"), ("test_sub_fail", "failed"), ("test_sub_fail", "failed"),
                                    # A failed subtest's enclosing one reports nothing; the next pair passes.
                                    ("test_sub_nested", "failed"), *[("test_sub_nested", "passed")] * 2,
                                    *[("test_sub_pass", "passed")] * 3, *[("test_unexpected_in_subtests", "passed")] * 2])
        # A failed subtest is reported apart: its test's own call passes.
        self.assertEqual(outcomes["test_unit.py::Derived::test_sub_fail", "call"], "passed")
        # In an expectedFailure test it is the failure expected, which ends the test.
        self.assertEqual(outcomes["test_unit.py::Derived::test_expected_in_subtest", "call"], "xfailed")
        self.assertEqual(outcomes["test_unit.py::Derived::test_unexpected_in_subtests", "call"], "failed")
        # A missing exception fails assertRaises with an AssertionError, which an outer one expects.
        self.assertEqual(outcomes["test_unit.py::Derived::test_raises_fails_as_an_assertion", "call"], "passed")
        self.assertEqual(outcomes["test_unit.py::test_subtest_outside_a_case_does_not_hide_its_failure", "call"],
                         "failed")
        self.assertEqual(runner.outcome_counts(results)["subtests passed"], 11)
        # Computed tables: pytest's IDs for values, names and objects.
        for case in ("test_range[2]", "test_named_comprehension[6]", "test_product[2-b]", "test_items[two-2]",
                     "test_dict_keys[one]", "test_objects[point1]", "test_named_objects[point0]",
                     "test_comprehension_of_objects[point2-7]", "test_named_values[ValueError]",
                     "test_named_values[make]", "test_joined[case2]", "test_joined[ten]", "test_joined[20]",
                     "test_mixed_ids[1]", "test_mixed_ids[two]", "test_mixed_ids[3]", "test_filtered[9]",
                     "test_folded[aaa]", "test_folded[16]", "test_folded[-1]", "test_folded[3.0]"):
            self.assertIn("test_tables.py::" + case, cases)
        # Marks from pytestmark, in the module and in a class.
        self.assertEqual(outcomes["test_marks.py::TestSkippedByAttribute::test_never", "setup"], "skipped")
        self.assertEqual(outcomes["test_marks.py::test_callable_raises_misses", "call"], "failed")
        self.assertEqual(outcomes["test_marks.py::test_callable_arguments_run_before_the_call", "call"], "failed")
        # The function is looked up, then the arguments are read, before the context is entered.
        self.assertEqual(outcomes["test_marks.py::test_callable_lookup_runs_before_the_context", "call"], "failed")
        self.assertEqual(outcomes["test_marks.py::test_callable_is_read_before_its_arguments", "call"], "passed")
        # A base class's tests come first; a helper class and the base itself are not collected.
        self.assertEqual([case.split("::", 1)[1] for case in cases if case.startswith("test_inherit.py::")], [
            "TestFirst::test_shared", "TestFirst::test_inherited_as_is", "TestFirst::test_own[1]",
            "TestFirst::test_own[2]", "TestFirst::test_overridden", "TestSecond::test_shared",
            "TestSecond::test_inherited_as_is", "TestSecond::test_own[1]", "TestSecond::test_own[2]",
            "TestSecond::test_overridden", "TestSecond::test_last"])
        failed = {nodeid.split("::", 1)[1] for (nodeid, phase), outcome in outcomes.items()
                  if nodeid.startswith("test_warns.py") and outcome == "failed"}
        self.assertEqual(failed, {"test_did_not_warn", "test_wrong_class", "test_match_misses",
                                  "test_exception_propagates", "Case::test_assert_warns_fails"})
        self.assertEqual(outcomes["test_xunit.py::TestSetupFails::test_never_runs", "setup"], "error")
        # Parameters annotated with pytest's own types take the values the runner passes.
        self.assertIn("test_hints.py::test_annotated_fixtures[b]", cases)
        self.assertNotIn("pytest.MonkeyPatch", generate(HINTS, "test_hints.py").source)
        self.assertEqual(outcomes["test_xunit.py::TestTeardownFails::test_passes", "teardown"], "error")

    def test_packages_nested_directories_and_layered_conftest(self):
        paths = self.files(PACKAGES)
        tree = runner.layout(paths, self.root)
        self.assertEqual([tree.modules[path] for path in paths], ["test_flat", "tests.test_area", "tests.unit.test_deep"])
        self.assertEqual(tree.packages, [self.root / "tests"])
        results, expected = self.run_paths(paths, "python")
        self.assertEqual([result.state for result in results], ["passed"] * 3, results[0].error + results[0].stderr)
        self.assertEqual(expected["cases"][-1], "tests/unit/test_deep.py::test_parent_package")
        self.assertEqual(len(expected["cases"]), 6)

    def test_imported_base_classes_and_cases(self):
        results, expected = self.run_paths(self.files(IMPORTED), "python")
        self.assertEqual([result.state for result in results], ["test-failed", "passed"])
        # pytest collects a unittest case in the module that imports it, under the name bound there.
        self.assertIn("tests/test_coptic.py::SharedCases::test_shared_one", expected["cases"])
        self.assertIn("tests/test_coptic.py::TestMore::test_shared_two", expected["cases"])
        self.assertEqual(len(expected["cases"]), 9)

    def test_bases_in_the_source_tree_and_module_attributes(self):
        results, expected = self.run_paths(self.files(RESOLVED), "python")
        self.assertEqual([result.state for result in results], ["test-failed"])
        # pytest collects an imported Test* class that has no constructor, and nothing from
        # one that has, from a function called Test* or from a module.
        self.assertEqual(expected["cases"], [
            "tests/test_resolved.py::TestKit::test_kit",
            "tests/test_resolved.py::LibraryCase::test_double",
            "tests/test_resolved.py::LibraryCase::test_fails",
            "tests/test_resolved.py::TestShared::test_inherited",
            "tests/test_resolved.py::TestShared::test_own",
            "tests/test_resolved.py::test_inert_names"])

    def test_builtin_fixtures_and_written_patches(self):
        results, expected = self.run_paths(self.files(FIXTURES), "python")
        self.assertEqual([result.state for result in results], ["passed"])
        self.assertEqual(len(expected["cases"]), 10)

    def test_output_capture_and_chdir(self):
        results, expected = self.run_paths(self.files(CAPTURE), "python")
        self.assertEqual([result.state for result in results], ["passed"])
        self.assertEqual(len(expected["cases"]), 6)

    def test_patch_forms_the_program_cannot_write(self):
        forms = {
            'monkeypatch.setattr("os.sep", "/")': "dotted name",
            'monkeypatch.setattr(os, name, "/")': 'setattr(target, "name", value)',
            'monkeypatch.setattr(os, "sep", "/", raising=False)': "raising=False",
            'monkeypatch.setattr(os, "sep", value="/")': "by position",
            'undo = monkeypatch.setattr(os, "sep", "/")': "statement of its own",
            'monkeypatch.setitem(os.environ, "A")': "setitem(mapping, key, value)",
            'monkeypatch.delitem(os.environ)': "delitem(mapping, key)",
            'monkeypatch.chdir()': "chdir(path)",
            'monkeypatch.delattr(os, "sep")': "monkeypatch.delattr is unsupported",
            'monkeypatch.syspath_prepend("x")': "monkeypatch.syspath_prepend is unsupported",
        }
        for statement, message in forms.items():
            source = f"import os\nname = 'sep'\ndef test_patch(monkeypatch):\n    {statement}\n"
            with self.subTest(statement=statement), self.assertRaisesRegex(CollectionError, re.escape(message)):
                generate(source, "test_patch.py")

    def test_bases_that_only_type_a_class(self):
        path = self.source("""
            import abc
            import typing
            from typing import Generic, Protocol, TypeVar
            T = TypeVar("T")
            class Api(Protocol):
                def run(self) -> int: ...
            class Mixin(Api):
                def test_mixin(self):
                    assert self.run() == 1
            class TestApi(Mixin):
                def run(self) -> int:
                    return 1
            class TestGeneric(Generic[T]):
                def test_generic(self):
                    assert True
            class TestAbstract(abc.ABC):
                def test_abstract(self):
                    assert True
            class TestQualified(typing.Protocol):
                def test_qualified(self):
                    assert True
        """, "test_markers.py")
        results, expected = self.run_paths([path], "python")
        self.assertEqual(results[0].state, "passed")
        # A Protocol has a constructor, so pytest collects no Test* class that derives from one.
        self.assertEqual(expected["cases"], ["test_markers.py::TestGeneric::test_generic",
                                             "test_markers.py::TestAbstract::test_abstract"])

    def test_forms_only_cpython_runs(self):
        # The collector follows pytest here; the compiler does not build these classes.
        path = self.source("""
            class Shared:
                def test_kept(self):
                    assert True
                def test_hidden(self):
                    assert False
            class TestHides(Shared):
                test_hidden = None
            def test_local_classes_are_not_collected():
                class TestLocal:
                    def test_inner(self) -> int:
                        return 1
                assert TestLocal().test_inner() == 1
        """, "test_python_only.py")
        results, expected = self.run_paths([path], "python")
        self.assertEqual(expected["cases"], ["test_python_only.py::TestHides::test_kept",
                                             "test_python_only.py::test_local_classes_are_not_collected"])
        self.assertEqual(results[0].state, "passed")

    def test_an_id_the_source_does_not_show_is_reported(self):
        # The value is read after import, as pytest reads it; the ID was read from the source.
        path = self.source("""
            import pytest
            VALUES = [1, 2]
            def change():
                VALUES[0] = 10
            @pytest.mark.parametrize("value", VALUES)
            def test_value(value):
                assert value in (10, 2)
            change()
        """, "test_stale.py")
        result = runner.run_module(path, self.root, self.work, "python", [], sys.executable, 60)
        expected = runner.oracle([path], self.root, self.work / "oracle", sys.executable, 60)
        self.assertEqual(result.state, "passed", result.error + result.stderr)
        self.assertEqual(result.cases[0], "test_stale.py::test_value[1]")
        self.assertEqual(expected["cases"][0], "test_stale.py::test_value[10]")
        self.assertIn("collected test IDs/order differ from pytest", runner.compare([result], expected))

    def run_cli(self, mode, *arguments):
        evidence = self.root / "evidence.json"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as error:
            status = runner.main([*arguments, "--root", str(self.root), "--mode", mode, "--work-dir", str(self.work),
                                  "--json", str(evidence), *(["--compiler", NATIVE] if mode != "python" else [])])
        return status, error.getvalue(), json.loads(evidence.read_text()) if evidence.exists() else {}

    def check_configured(self, mode):
        self.files({**CONFIGURED, "tests/conftest.py": HOOKS, "tests/test_selected.py": SELECTED}, True)
        # (A caller that has not read the configuration must not run under it.)
        with self.assertRaisesRegex(CollectionError, "pytest configuration is not supported"):
            runner.discover([self.root], self.root)
        status, error, report = self.run_cli(mode, str(self.root / "tests"))
        self.assertEqual(status, 1, error)
        self.assertEqual(report["qualification"], "pytest-matched", error)
        outcomes = {event["nodeid"].split("::")[1]: event["outcome"] for event in report["results"][0]["events"]
                    if event["phase"] == "call"}
        # xfail_strict, pythonpath, -W error::DeprecationWarning and filterwarnings apply.
        self.assertEqual(outcomes, {
            "test_imports_from_pythonpath": "passed", "test_strict_xpass_fails": "failed", "test_xfail": "xfailed",
            "test_deprecation_is_an_error": "failed", "test_expected_warning": "passed"})
        # Names for marks, filterwarnings marks over the configuration's filters, and recwarn.
        selected = {event["nodeid"].split("::")[1]: event["outcome"] for event in report["results"][1]["events"]
                    if event["phase"] == "call"}
        self.assertEqual(selected, dict.fromkeys([
            "test_alias_quiets_the_configured_error", "test_marker_registered_by_a_hook", "test_alias_table[1]",
            "test_alias_table[2]", "test_alias_condition", "test_mark_overrides_the_configured_ignore",
            "test_the_outer_mark_wins", "test_recwarn"], "passed"))
        # The hooks pytest ran are not in the program: its report names them.
        self.assertEqual(report["results"][0]["hooks"], [
            "tests/conftest.py: " + hook for hook in ("pytest_addoption", "pytest_configure",
                                                       "pytest_collection_modifyitems")])

    def test_project_configuration_is_honored(self):
        self.check_configured("python")
        settings = runner.configuration([self.root / "tests" / "test_config.py"], self.root)
        self.assertTrue(settings.xfail_strict)
        self.assertEqual(settings.pythonpath, [(self.root / "src").resolve()])
        self.assertEqual(settings.filters, [("error", "", "DeprecationWarning"), ("ignore", "harmless", "UserWarning")])
        self.assertIn("addopts = --strict-markers", settings.ini)

    def test_expressions_select_cases_as_pytest_does(self):
        self.files({**CONFIGURED, "tests/conftest.py": HOOKS, "tests/test_selected.py": SELECTED}, True)
        tests = str(self.root / "tests")

        def chosen(*arguments):
            status, error, report = self.run_cli("python", tests, *arguments)
            self.assertEqual(report.get("qualification"), "pytest-matched", error)
            return status, [case.split("::")[1] for result in report["results"] for case in result["cases"]]

        self.assertEqual(chosen("-m", "slow"), (0, ["test_imports_from_pythonpath",
                                                    "test_alias_quiets_the_configured_error"]))
        self.assertEqual(chosen("-k", "alias and not table"), (0, ["test_alias_quiets_the_configured_error",
                                                                   "test_alias_condition"]))
        # -k reads a test's module and marks too, in any letter case; -m its marks by name.
        self.assertEqual(len(chosen("-k", "TEST_SELECTED")[1]), 8)
        self.assertEqual(chosen("-k", "filterwarnings or parametrize")[1], [
            "test_alias_quiets_the_configured_error", "test_alias_table[1]", "test_alias_table[2]",
            "test_mark_overrides_the_configured_ignore", "test_the_outer_mark_wins"])
        self.assertEqual(chosen("-m", "not (slow or xfail or filterwarnings) and not parametrize", "-k", "selected")[1],
                         ["test_marker_registered_by_a_hook", "test_alias_condition", "test_recwarn"])
        self.assertEqual(chosen("-k", "table[2]")[1], ["test_alias_table[2]"])
        self.assertEqual(chosen("-k", "no_such_test"), (5, []))
        # Node IDs are chosen first; the expressions then choose among them.
        status, error, report = self.run_cli("python", tests + "/test_selected.py::test_alias_table", "-k", "1")
        self.assertEqual((status, report["results"][0]["cases"]), (0, ["tests/test_selected.py::test_alias_table[1]"]),
                         error)
        # The configuration's own -m applies, and the command line's replaces it.
        (self.root / "pytest.ini").write_text("[pytest]\naddopts = -m slow\npythonpath = src\n"
                                              "markers =\n    slow: takes a while\n")
        (self.root / "pyproject.toml").unlink()
        self.assertEqual(len(chosen()[1]), 2)
        # The conftest.py hook marks the slow tests as net too, which the program cannot
        # know: pytest selects three tests, the program one, and the run is an error.
        status, error, report = self.run_cli("python", tests, "-m", "net")
        self.assertEqual((status, report["qualification"]), (2, "pytest-mismatch"), error)
        self.assertIn("tests/conftest.py: pytest_collection_modifyitems", error)
        for expression in ("(", "a and", "not", "slow(a=1)", "a b"):
            with self.subTest(expression=expression):
                status, error, _ = self.run_cli("python", tests, "-k", expression)
                self.assertEqual(status, 2)
                self.assertIn("unsupported -k expression", error)

    def test_hooks_need_the_comparison_that_answers_for_them(self):
        files = {"conftest.py": "import pytest\n\n\ndef pytest_collection_modifyitems(items):\n"
                                "    for item in items:\n        if 'slow' in item.keywords:\n"
                                "            item.add_marker(pytest.mark.skip(reason='slow'))\n",
                 "test_a.py": "import pytest\n\n\n@pytest.mark.slow\ndef test_slow():\n    assert True\n\n\n"
                              "def test_fast():\n    assert True\n"}
        self.files(files)
        # pytest skips what the hook marks and the program runs it: the difference is an error.
        status, error, report = self.run_cli("python", str(self.root))
        self.assertEqual((status, report["qualification"]), (2, "pytest-mismatch"), error)
        self.assertIn("does not run these conftest.py hooks", error)
        self.assertIn("conftest.py: pytest_collection_modifyitems", error)
        # Where the hook changes nothing that ran, the run is verified.
        status, error, report = self.run_cli("python", str(self.root), "-k", "fast")
        self.assertEqual((status, report["qualification"]), (0, "pytest-matched"), error)
        # Without the comparison nothing answers for the hook.
        status, error, report = self.run_cli("python", str(self.root), "--no-compare")
        self.assertEqual(status, 2)
        self.assertIn("pytest_collection_modifyitems is not run natively", report["results"][0]["error"])

    def test_configuration_the_runner_cannot_honor_is_rejected(self):
        path = self.source("def test_a(): pass\n", "tests/test_a.py")
        rejected = {
            "pyproject.toml": [('[tool.pytest.ini_options]\naddopts = "-n auto"\n', "addopts '-n'"),
                               ('[tool.pytest.ini_options]\naddopts = "-x"\n', "addopts '-x'"),
                               ('[tool.pytest.ini_options]\npython_files = "check_*.py"\n', "python_files"),
                               ('[tool.pytest.ini_options]\nasyncio_mode = "auto"\n', "asyncio_mode"),
                               ('[tool.pytest.ini_options]\nfilterwarnings = ["error::pkg.Custom"]\n',
                                "filterwarnings 'error::pkg.Custom'"),
                               ("[tool.pytest.ini_options\n", "cannot read pytest configuration")],
            "pytest.ini": [("[pytest]\npython_functions = check_*\n", "python_functions"),
                           ("[pytest]\nusefixtures = clean\n", "usefixtures")],
            "setup.cfg": [("[tool:pytest]\ndoctest_optionflags = ELLIPSIS\n", "doctest_optionflags")],
        }
        for name, cases in rejected.items():
            for content, message in cases:
                with self.subTest(name=name, content=content):
                    (self.root / name).write_text(content)
                    try:
                        status, error, _ = self.run_cli("python", str(path))
                        self.assertEqual(status, 2)
                        self.assertIn("pytest configuration", error)
                        self.assertIn(message, error)
                    finally:
                        (self.root / name).unlink()
        # A project file that does not configure pytest, and options that only shape its report.
        accepted = {"pyproject.toml": '[project]\nname = "x"\n[tool.ruff]\nline-length = 100\n',
                    "tox.ini": "[tox]\nenvlist = py\n",
                    "pytest.ini": "[pytest]\naddopts = -q -ra --tb=short --color yes\nlog_level = INFO\n"
                                  "testpaths = tests\njunit_family = xunit2\n"}
        for name, content in accepted.items():
            (self.root / name).write_text(content)
        status, error, report = self.run_cli("python", str(path))
        self.assertEqual((status, report["qualification"]), (0, "pytest-matched"), error)
        # The nearest file is the one pytest reads.
        (self.root / "tests" / "pytest.ini").write_text("[pytest]\nxfail_strict = true\n")
        self.assertTrue(runner.configuration([path], self.root).xfail_strict)
        self.assertEqual(runner.configuration([path], self.root).source, str(self.root / "tests" / "pytest.ini"))

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_jit_project_configuration(self):
        self.check_configured("jit")

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_jit_suites_under_gc_stress(self):
        # A unittest case's object and a module's parameter tables must survive each test.
        with patch.dict(os.environ, {"PYSTACHY_GC_STRESS_PROGRAM": "1", "PYSTACHY_IRCHECK": "1"}):
            results, _ = self.suites("jit")
        self.assertTrue(results[0].assertion_operands, results[0].operand_build_error)

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_aot_packages(self):
        results, _ = self.run_paths(self.files(PACKAGES), "aot")
        self.assertEqual([result.state for result in results], ["passed"] * 3, results[0].error + results[0].stderr)

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_jit_imported_base_classes(self):
        results, _ = self.run_paths(self.files(IMPORTED), "jit")
        self.assertEqual([result.state for result in results], ["test-failed", "passed"])

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_jit_builtin_fixtures_and_written_patches(self):
        results, _ = self.run_paths(self.files(FIXTURES), "jit")
        self.assertEqual([result.state for result in results], ["passed"], results[0].error + results[0].stderr)

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_jit_output_capture_and_chdir(self):
        probe = self.source(DESCRIPTORS, "descriptors.py")
        built = subprocess.run([*shlex.split(NATIVE), "ir", str(probe), "-o", os.devnull], capture_output=True)
        probe.unlink()
        if built.returncode:
            self.skipTest("this compiler has no os.dup, os.dup2, os.close and os.chdir")
        results, _ = self.run_paths(self.files(CAPTURE), "jit")
        self.assertEqual([result.state for result in results], ["passed"], results[0].error + results[0].stderr)

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_jit_bases_in_the_source_tree(self):
        results, _ = self.run_paths(self.files(RESOLVED), "jit")
        self.assertEqual([result.state for result in results], ["test-failed"])


@unittest.skipUnless(importlib.util.find_spec("pytest"), "real pytest required for independent oracle")
class UncompiledTests(TemporarySuite):
    """A test the compiler rejects is left out and reported; the others run."""

    def files(self, files):
        for name, text in files.items():
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text(text)
        return runner.discover([self.root], self.root)

    def rejecting(self):
        # (Not beside the tests: CPython would import those in place of the generated modules.)
        compiler = self.root / "compiler" / "rejecting.py"
        compiler.parent.mkdir(exist_ok=True)
        compiler.write_text(REJECTING_COMPILER)
        return [sys.executable, str(compiler)]

    def run_rejecting(self, files, *arguments):
        paths = self.files(files)
        evidence = self.root / "evidence.json"
        with contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as error:
            status = runner.main([*(arguments or [str(path) for path in paths]), "--root", str(self.root),
                                  "--mode", "jit", "--work-dir", str(self.work), "--json", str(evidence),
                                  "--compiler", shlex.join(self.rejecting())])
        return status, output.getvalue(), error.getvalue(), json.loads(evidence.read_text())

    def test_the_line_a_diagnostic_blames(self):
        files = {"/w/tests/test_a.py": 0, "/w/test_a.py": 1}
        text = ("/w/pkg/core.py:9: error: expected int, got str (compiling pkg.core.f(str) for the call at "
                "/w/test_a.py:12; compiling test_a.test_x(str) for the call at /w/tests/test_a.py:140)\n")
        self.assertEqual(runner.blamed_lines(text, files), [(1, 12), (0, 140)])
        self.assertEqual(runner.blamed_lines(text, {}), [])
        source = textwrap.dedent(REJECTED)
        cases = ["t.py::test_first", "t.py::test_marked[1]", "t.py::TestGroup::test_kept",
                 "t.py::TestGroup::test_method", "t.py::TestWhole::test_one"]
        lines = source.split("\n")

        def at(text):
            return lines.index(text) + 1
        # A decorated test from its first decorator; a method alone; a class for its other lines.
        self.assertEqual(runner.test_region(source, at("    REJECTED = value"), cases),
                         (at("@pytest.mark.parametrize("), at("    assert REJECTED"), "test_marked"))
        self.assertEqual(runner.test_region(source, at("        REJECTED = 1"), cases),
                         (at('    @pytest.mark.skip(reason="never")'), at("        REJECTED = 1"), "TestGroup::test_method"))
        self.assertEqual(runner.test_region(source, at("        LOG.append(\"setup\")"), cases),
                         (at("class TestGroup:"), at("        assert helper() == 1"), "TestGroup"))
        # Before a module has cases, a test is what its name says, and any class may hold some.
        self.assertEqual(runner.test_region(source, at("    assert LOG[0] == \"first\""), None)[2], "test_last")
        self.assertEqual(runner.test_region(source, at("    REJECTED = 1"), None)[2], "TestWhole")
        self.assertIsNone(runner.test_region(source, at("    return 1"), None))
        # A helper, a module statement and a class no case names belong to no test.
        self.assertIsNone(runner.test_region(source, at("    return 1"), cases))
        self.assertIsNone(runner.test_region(source, at("LOG: list[str] = []"), cases))
        self.assertIsNone(runner.test_region(source, at("    REJECTED = 1"), cases[:4]))
        self.assertIsNone(runner.test_region("def broken(:\n", 1, cases))
        blank = runner.blanked(source, at("    def test_kept(self):"), at("        assert LOG[-1] == \"setup\""))
        self.assertEqual(len(blank.split("\n")), len(lines))
        self.assertEqual(blank.split("\n")[at("    def test_kept(self):") - 1], "    pass")
        self.assertEqual(blank.split("\n")[at("def test_last():") - 1], "def test_last():")

    def test_rejected_tests_are_left_out_and_the_run_fails(self):
        status, output, error, report = self.run_rejecting({"test_rejected.py": REJECTED})
        result = report["results"][0]
        self.assertEqual(status, 2, error)
        self.assertEqual(report["qualification"], "partial", error)
        self.assertEqual(report["differences"], [runner.LEFT_OUT])
        self.assertEqual(result["state"], "passed", error)
        self.assertEqual([case.split("::", 1)[1] for case in result["cases"]],
                         ["test_first", "TestGroup::test_kept", "TestGroup::test_also_kept", "test_last"])
        self.assertEqual({case.split("::", 1)[1] for case in result["uncompiled"]},
                         {"test_marked[1]", "test_marked[2]", "TestGroup::test_method", "TestWhole::test_one",
                          "TestWhole::test_two"})
        # The reason names the test's own line beside the generated one.
        self.assertRegex(result["uncompiled"]["test_rejected.py::test_marked[1]"],
                         r"^test_rejected\.py:\d+ \[generated test_rejected\.py:\d+\]: error: rejected")
        self.assertIn("NOT COMPILED test_rejected.py::TestWhole::test_two", output)
        self.assertIn("4 passed, 5 not compiled", output)
        self.assertIn("match for the cases the program has", output)
        # pytest ran them: a skipped one and four that passed.
        self.assertIn("test_rejected.py::TestGroup::test_method: pytest skipped, native not compiled",
                      report["mismatches"])
        self.assertIn("test_rejected.py::test_marked[2]: pytest passed, native not compiled", report["mismatches"])
        self.assertEqual(len(report["mismatches"]), 5)
        # Without the comparison the run fails as well.
        status, output, error, report = self.run_rejecting({}, str(self.root / "test_rejected.py"), "--no-compare")
        self.assertEqual((status, report["qualification"]), (2, "unverified"), error)
        self.assertEqual(len(report["results"][0]["uncompiled"]), 5)

    def test_imports_the_compiler_cannot_make_are_left_out_with_their_users(self):
        status, output, error, report = self.run_rejecting({
            "values.py": "KEPT = 1\nREJECTED_name = 2\nother = 3\n", "test_imports.py": UNIMPORTED})
        result = report["results"][0]
        self.assertEqual(status, 2, error)
        self.assertEqual(report["qualification"], "partial", error)
        self.assertEqual([case.split("::", 1)[1] for case in result["cases"]],
                         ["test_uses_the_others", "TestGroup::test_kept"])
        # The module's import goes whole; the from-import loses the one name it lacks.
        self.assertEqual(list(result["unbound"]), [
            "test_imports.py:4: import json as REJECTED_json",
            "test_imports.py:6: from values import ( KEPT, REJECTED_name, other as renamed, ) (REJECTED_name)"])
        self.assertIn("error: module 'missing' is not supported",
                      result["unbound"]["test_imports.py:4: import json as REJECTED_json"])
        self.assertEqual({case.split("::", 1)[1] for case in result["uncompiled"]},
                         {"test_uses_the_module", "test_uses_the_name", "TestGroup::test_method_uses_the_module"})
        # A test left out for such a name gives both diagnostics.
        self.assertRegex(result["uncompiled"]["test_imports.py::test_uses_the_name"],
                         r"error: name 'REJECTED_name' is not defined; what binds it was left out: "
                         r"test_imports\.py:6 \[generated test_imports\.py:\d+\]: error: cannot import name")
        self.assertIn("NOT BOUND test_imports.py:4: import json as REJECTED_json", output)
        self.assertIn("2 passed, 3 not compiled, 2 statements left out", output)

    def test_an_import_left_out_is_no_success_though_no_test_uses_it(self):
        status, output, error, report = self.run_rejecting({"test_unused.py": textwrap.dedent("""
            import json as REJECTED_json

            def test_only():
                assert True
        """)})
        self.assertEqual(status, 2, error)
        self.assertEqual(report["qualification"], "partial")
        self.assertEqual(report["results"][0]["cases"], ["test_unused.py::test_only"])
        self.assertEqual(report["results"][0]["uncompiled"], {})
        self.assertIn("1 passed, 1 statement left out", output)
        self.assertEqual(report["mismatches"], [])

    def test_imports_that_are_not_left_out(self):
        future = "from __future__ import annotations, REJECTED_x\n"
        self.assertIsNone(runner.binding_region(future, 1, "REJECTED_x"))
        self.assertIsNone(runner.binding_region("from values import *\n", 1))
        self.assertIsNone(runner.binding_region("try:\n    import x\nexcept ImportError:\n    pass\n", 2))
        self.assertIsNone(runner.binding_region("def f():\n    import x\n", 2))
        self.assertEqual(runner.binding_region("import a.b, c as d\n", 1), (1, 1, ["a", "d"], "pass"))
        self.assertEqual(runner.binding_region("from m import (a,\n  b as c)\n", 2, "b"), (1, 2, ["c"], "from m import a"))
        # An assignment of names; not one of a name pytest reads by itself, nor of anything but names.
        self.assertEqual(runner.binding_region("A: int = (\n  1)\n", 2), (1, 2, ["A"], "pass"))
        self.assertEqual(runner.binding_region("a = b = 1\n", 1), (1, 1, ["a", "b"], "pass"))
        for statement in ("pytestmark = 1", "pytest_plugins = ['x']", "collect_ignore = []", "__test__ = False",
                          "a, b = 1, 2", "a.b = 1", "a[0] = 1", "import pytest", "from x import pytest_configure",
                          "a += 1", "print(1)"):
            self.assertIsNone(runner.binding_region(statement + "\n", 1), statement)
        # The only name of a from-import takes the statement with it.
        self.assertEqual(runner.binding_region("from m import a\n", 1, "a"), (1, 1, ["a"], "pass"))
        self.assertEqual(runner.blanked("from m import (a,\n  b)\nx = 1\n", 1, 2, "from m import a"),
                         "from m import a\n\nx = 1\n")

    def run_python(self, files, *arguments):
        paths = self.files(files)
        evidence = self.root / "evidence.json"
        with contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as error:
            status = runner.main([*(arguments or [str(path) for path in paths]), "--root", str(self.root),
                                  "--mode", "python", "--work-dir", str(self.work), "--json", str(evidence)])
        return status, output.getvalue(), error.getvalue(), json.loads(evidence.read_text())

    def test_tests_the_collector_rejects_are_left_out(self):
        status, output, error, report = self.run_python({"test_mixed.py": UNCOLLECTED})
        result = report["results"][0]
        self.assertEqual(status, 2, error)
        self.assertEqual(report["qualification"], "partial", error)
        self.assertEqual(report["differences"], [runner.LEFT_OUT])
        self.assertEqual([case.split("::", 1)[1] for case in result["cases"]],
                         ["test_plain", "TestGroup::test_kept", "test_last"])
        reasons = {name.split("::", 1)[1]: reason for name, reason in result["uncollected"].items()}
        self.assertEqual(set(reasons), {"test_table", "test_patched", "test_dotted", "TestBoth", "TestDerived",
                                        "TestGroup::test_method_table"})
        self.assertIn("parametrize needs a table the collector can read", reasons["test_table"])
        self.assertIn("several base classes", reasons["TestBoth"])
        # A class goes with the base class it derives from.
        self.assertIn("its base class was left out: test_mixed.py:", reasons["TestDerived"])
        self.assertEqual(list(result["unbound"]), ["test_mixed.py:3: from unittest import mock"])
        self.assertEqual(result["uncompiled"], {})
        # Every case pytest ran of those tests is named, with pytest's outcome.
        self.assertEqual(len(report["mismatches"]), 13, report["mismatches"])
        self.assertIn("test_mixed.py::test_table[2]: pytest passed, native not collected", report["mismatches"])
        self.assertIn("test_mixed.py::TestDerived::test_a: pytest passed, native not collected", report["mismatches"])
        self.assertIn("NOT COLLECTED test_mixed.py::TestGroup::test_method_table", output)
        self.assertIn("3 passed, 6 tests not collected, 1 statement left out", output)
        self.assertIn("match for the cases the program has", output)
        # Without the comparison the run fails as well.
        status, _, error, report = self.run_python({}, str(self.root / "test_mixed.py"), "--no-compare")
        self.assertEqual((status, report["qualification"]), (2, "unverified"), error)

    def test_fixtures_the_collector_rejects_are_left_out_with_the_tests_that_request_them(self):
        rejected = "@pytest.fixture\ndef {name}(request):\n    return request.node.name\n"
        status, output, error, report = self.run_python({
            "conftest.py": "import pytest\n@pytest.fixture\ndef plain():\n    return 1\n"
                           + rejected.format(name="node_name") + rejected.format(name="tmp_path")
                           + "@pytest.fixture\ndef through(node_name):\n    return node_name.upper()\n",
            "test_outer.py": textwrap.dedent("""
                import pytest

                def test_plain(plain):
                    assert plain == 1

                def test_named(node_name):
                    assert node_name == "test_named"

                def test_through(through):
                    assert through == "TEST_THROUGH"

                def test_builtin_name(tmp_path):
                    assert tmp_path == "test_builtin_name"

                @pytest.fixture(name="renamed")
                def local(request):
                    return request.node.name

                def test_local(renamed):
                    assert renamed == "test_local"

                @pytest.mark.usefixtures("node_name")
                class TestMarked:
                    def test_method(self):
                        assert True
            """),
            # A nearer conftest.py that defines the name provides it again, also to the wider one's fixtures.
            "inner/conftest.py": "import pytest\n@pytest.fixture\ndef node_name():\n    return 'inner'\n",
            "inner/test_inner.py": "def test_redefined(node_name, through):\n"
                                   "    assert (node_name, through) == ('inner', 'INNER')\n",
        })
        self.assertEqual(status, 2, error)
        self.assertEqual(report["qualification"], "partial", error)
        inner, outer = report["results"]
        self.assertEqual((inner["cases"], outer["cases"]),
                         (["inner/test_inner.py::test_redefined"], ["test_outer.py::test_plain"]))
        # A conftest.py's are on the first module.
        self.assertEqual(list(inner["unavailable"]), ["conftest.py::node_name", "conftest.py::tmp_path"])
        self.assertEqual(list(outer["unavailable"]), ["test_outer.py::renamed"])
        reasons = {name.split("::", 1)[1]: reason for name, reason in outer["uncollected"].items()}
        self.assertEqual(set(reasons), {"test_named", "test_through", "test_builtin_name", "test_local",
                                        "TestMarked::test_method"})
        self.assertIn("the fixture node_name was left out: conftest.py:", reasons["test_through"])
        # pytest's own fixture of the name does not take the place of the one left out.
        self.assertIn("the fixture tmp_path was left out", reasons["test_builtin_name"])
        self.assertIn("the fixture renamed was left out: test_outer.py:", reasons["test_local"])
        self.assertIn("NOT AVAILABLE conftest.py::node_name (fixture)", output)
        self.assertIn("2 passed, 5 tests not collected, 3 fixtures left out", output)
        self.assertEqual(len(report["mismatches"]), 5, report["mismatches"])

    def test_fixtures_that_are_not_left_out(self):
        source = "import pytest\n@pytest.fixture({})\ndef value(request):\n    return request.node\n"
        self.assertEqual(runner.fixture_region(source.format(""), 4), (2, 4, "value"))
        self.assertEqual(runner.fixture_region(source.format("name='other', scope='module'"), 3), (2, 4, "other"))
        self.assertEqual(runner.fixture_region("import pytest\n@pytest.fixture\ndef value():\n    pass\n", 3),
                         (2, 4, "value"))
        for options in ("autouse=True", "autouse=FLAG", "name=NAME", "**OPTIONS"):
            self.assertIsNone(runner.fixture_region(source.format(options), 4), options)
        self.assertIsNone(runner.fixture_region("def helper():\n    pass\n", 2))
        self.assertIsNone(runner.fixture_region("class A:\n    @pytest.fixture\n    def value(self):\n        pass\n", 4))

    def test_what_the_collector_rejects_outside_tests_rejects_the_module(self):
        fixture = ("import pytest\n@pytest.fixture(autouse=True)\ndef value(request):\n"
                   "    return request.node.name\n")
        cases = {
            "fixture": ({"test_whole.py": fixture + "def test_a(value):\n    assert value\n"}, "test_whole.py:"),
            "module statement": ({"test_whole.py": "def helper(): pass\nglobals()['test_alias'] = helper\n"
                                                   "def test_a(): pass\n"}, "namespace inspection"),
            "star import": ({"values.py": "X = 1\n", "test_whole.py": "from values import *\ndef test_a(): pass\n"},
                            "star imports"),
            "conftest": ({"conftest.py": fixture, "test_whole.py": "def test_a(value):\n    assert value\n"},
                         "conftest.py:"),
        }
        for name, (files, message) in cases.items():
            with self.subTest(name):
                for stale in self.root.glob("*.py"):
                    stale.unlink()
                self.work = self.root / "build" / name.replace(" ", "-")
                status, _, error, report = self.run_python(files)
                result = report["results"][-1]
                self.assertEqual((status, result["state"]), (2, "collection-error"), error)
                self.assertIn(message, result["error"])
                self.assertEqual((result["uncollected"], result["unbound"], result["unavailable"]), ({}, {}, {}))

    def test_the_tests_not_collected_are_bounded(self):
        source = "".join(f"async def test_{index}(): pass\n" for index in range(3)) + "def test_ok(): pass\n"
        with patch.object(runner, "UNCOLLECTED_LIMIT", 2):
            status, _, error, report = self.run_python({"test_many.py": source})
        self.assertEqual((status, report["results"][0]["state"]), (2, "collection-error"), error)
        self.work = self.root / "build" / "enough"
        with patch.object(runner, "UNCOLLECTED_LIMIT", 3):
            status, _, error, report = self.run_python({"test_many.py": source})
        self.assertEqual((status, report["results"][0]["state"]), (2, "passed"), error)
        self.assertEqual(len(report["results"][0]["uncollected"]), 3)

    def test_other_differences_are_still_differences(self):
        # The test left out is the one that made a later test pass under pytest.
        status, _, error, report = self.run_rejecting({"test_order.py": textwrap.dedent("""
            LOG: list[str] = []

            def test_writes():
                REJECTED = 1
                LOG.append("written")

            def test_reads():
                assert LOG == ["written"]
        """)})
        self.assertEqual(status, 2, error)
        self.assertEqual(report["qualification"], "pytest-mismatch")
        self.assertIn("test_order.py::test_reads [call]: pytest passed, native failed", report["mismatches"])
        self.assertEqual(list(report["results"][0]["uncompiled"]), ["test_order.py::test_writes"])

    def test_errors_no_test_explains_fail_the_build(self):
        fixture = "import pytest\n@pytest.fixture({})\ndef value():\n    REJECTED = 1\n    return REJECTED\n"
        for name, files in (
                ("module statement", {"test_whole.py": "print('REJECTED')\ndef test_a():\n    assert True\n"}),
                ("helper", {"test_whole.py": "def helper():\n    REJECTED = 1\n    return REJECTED\n"
                                             "def test_a():\n    assert helper()\n"}),
                ("autouse fixture", {"test_whole.py": fixture.format("autouse=True") + "def test_a():\n    assert True\n"})):
            with self.subTest(name):
                self.work = self.root / "build" / name.replace(" ", "-")
                status, _, error, report = self.run_rejecting(files)
                result = report["results"][0]
                self.assertEqual(status, 2)
                # (A JIT command that fails before the program starts is an execution error.)
                self.assertEqual(result["state"], "execution-error")
                self.assertEqual((result["uncompiled"], result["unbound"], result["unavailable"]), ({}, {}, {}))
                self.assertIn("error: rejected", error)

    def test_fixtures_and_bindings_the_compiler_rejects_are_left_out(self):
        fixture = "@pytest.fixture\ndef {name}():\n    REJECTED = 1\n    return REJECTED\n"
        status, output, error, report = self.run_rejecting({
            "conftest.py": "import pytest\nSHARED = 'REJECTED'\n" + fixture.format(name="shared") + textwrap.dedent("""
                @pytest.fixture
                def plain():
                    return 1
            """),
            "test_fixtures.py": "import pytest\nREJECTED_table = [1]\n" + fixture.format(name="local") + textwrap.dedent("""
                def test_plain(plain):
                    assert plain == 1

                def test_shared(shared):
                    assert shared == 1

                def test_local(local, plain):
                    assert local == plain

                def test_table():
                    assert REJECTED_table
            """)})
        result = report["results"][0]
        self.assertEqual(status, 2, error)
        self.assertEqual(report["qualification"], "partial", error)
        self.assertEqual(result["cases"], ["test_fixtures.py::test_plain"])
        self.assertEqual(set(result["unavailable"]), {"conftest.py::shared", "test_fixtures.py::local"})
        self.assertEqual(set(result["unbound"]), {"conftest.py:2: SHARED = 'REJECTED'",
                                                  "test_fixtures.py:2: REJECTED_table = [1]"})
        # The tests that request a fixture left out are not collected; the one that reads the name does not build.
        self.assertEqual({name.split("::")[1] for name in result["uncollected"]}, {"test_shared", "test_local"})
        self.assertIn("the fixture shared was left out: conftest.py:", result["uncollected"]["test_fixtures.py::test_shared"])
        self.assertEqual(list(result["uncompiled"]), ["test_fixtures.py::test_table"])
        self.assertIn("what binds it was left out: test_fixtures.py:2", result["uncompiled"]["test_fixtures.py::test_table"])
        self.assertIn("1 passed, 2 tests not collected, 1 not compiled, 2 statements left out, 2 fixtures left out", output)

    def test_a_selected_test_is_not_left_out(self):
        status, _, error, report = self.run_rejecting({"test_rejected.py": REJECTED},
                                                      str(self.root / "test_rejected.py") + "::test_marked")
        self.assertEqual(status, 2)
        self.assertEqual(report["results"][0]["state"], "execution-error", error)
        self.assertEqual(report["results"][0]["uncompiled"], {})

    def test_the_tests_left_out_are_bounded(self):
        source = "".join(f"def test_{index}():\n    REJECTED = {index}\n" for index in range(4)) + "def test_ok(): pass\n"
        with patch.object(runner, "LEFT_OUT_LIMIT", 3):
            status, _, error, report = self.run_rejecting({"test_many.py": source})
        self.assertEqual(status, 2)
        self.assertEqual(report["results"][0]["state"], "execution-error", error)
        self.assertEqual(len(report["results"][0]["uncompiled"]), 3)
        self.work = self.root / "build" / "enough"
        with patch.object(runner, "LEFT_OUT_LIMIT", 4):
            status, _, error, report = self.run_rejecting({"test_many.py": source})
        self.assertEqual((status, report["results"][0]["state"]), (2, "passed"), error)
        self.assertEqual(report["results"][0]["cases"], ["test_many.py::test_ok"])

    def test_every_test_left_out_is_no_success(self):
        status, _, error, report = self.run_rejecting({"test_none.py": "def test_only():\n    REJECTED = 1\n"})
        self.assertEqual(status, 2, error)
        self.assertEqual(report["results"][0]["state"], "empty", error)
        self.assertEqual(list(report["results"][0]["uncompiled"]), ["test_none.py::test_only"])

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_jit_and_aot_leave_out_what_the_compiler_rejects(self):
        paths = self.files({"test_left.py": UNCOMPILED})
        for mode in ("jit", "aot"):
            with self.subTest(mode=mode):
                results = runner.run_suite(paths, self.root, self.work / mode, mode, shlex.split(NATIVE),
                                           sys.executable, 300)
                expected = runner.oracle(paths, self.root, self.work / "oracle", sys.executable, 120)
                self.assertEqual(runner.compare(results, expected), [runner.LEFT_OUT],
                                 results[0].error + results[0].stderr)
                self.assertEqual(results[0].state, "passed", results[0].stderr)
                self.assertEqual({case.split("::", 1)[1] for case in results[0].uncompiled}, UNCOMPILED_CASES)
                self.assertEqual([case.split("::", 1)[1] for case in results[0].cases],
                                 ["test_first", "TestGroup::test_fine", "TestGroup::test_last", "test_end"])
                # The calls that led the compiler to the rejected line blame the test.
                self.assertIn("compiling test_left.twice(str)", results[0].uncompiled["test_left.py::test_values[3]"])
                # A module the compiler does not have: its import goes, then the test that uses it.
                self.assertEqual(list(results[0].unbound), ["test_left.py:2: import dis"])
                self.assertRegex(results[0].uncompiled["test_left.py::test_bytecode"],
                                 "name 'dis' is not defined; what binds it was left out: .*module 'dis' is not supported")
                self.assertTrue(results[0].assertion_operands)


CONSTANTS = {
    "pkg/__init__.py": "from .constants import ALPHABET, LIMIT\n",
    "pkg/constants.py": 'ALPHABET = "abc"\nLIMIT: int = 5\nRATIO = 0.5\nNAMES = ["a", "b"]\n'
                        "TWICE = 1\nTWICE = 2\nMADE = len(ALPHABET)\nKEPT = 7\n\n\n"
                        "def change():\n    global KEPT\n    KEPT = 8\n",
    "tests/test_ids.py": textwrap.dedent("""
        import pytest
        from pkg import ALPHABET, LIMIT as TOP
        from pkg.constants import RATIO, NAMES


        @pytest.mark.parametrize("size, text", [
            (len(ALPHABET) + 0, "abc"),
            (len(ALPHABET) + 1, ALPHABET + "d"),
            (TOP, ALPHABET),
            pytest.param(TOP * 2, "x" * TOP, id="named"),
        ])
        def test_sizes(size, text):
            assert size >= 3
            assert isinstance(text, str)


        @pytest.mark.parametrize("ratio", [RATIO, RATIO * 2, -TOP])
        def test_ratio(ratio):
            assert ratio != 0


        @pytest.mark.parametrize("names", [NAMES, [ALPHABET]])
        def test_names(names):
            assert len(names) >= 1
    """),
}
CONSTANT_IDS = ["test_sizes[3-abc]", "test_sizes[4-abcd]", "test_sizes[5-abc]", "test_sizes[named]",
                "test_ratio[0.5]", "test_ratio[1.0]", "test_ratio[-5]", "test_names[names0]", "test_names[names1]"]


@unittest.skipUnless(importlib.util.find_spec("pytest"), "real pytest required for independent oracle")
class ImportedConstantTests(TemporarySuite):
    """A case is named after a value computed from a constant another module binds."""

    files = UncompiledTests.files
    run_python = UncompiledTests.run_python

    def test_ids_follow_constants_of_modules_beside_the_tests(self):
        status, _, error, report = self.run_python(CONSTANTS, str(self.root / "tests"))
        self.assertEqual((status, report["qualification"]), (0, "pytest-matched"), error + json.dumps(report))
        self.assertEqual([case.split("::", 1)[1] for case in report["results"][0]["cases"]], CONSTANT_IDS)
        # The program checks each value an ID was read from; a named case and a list need none.
        generated = "".join(path.read_text() for path in self.work.rglob("test_ids.py"))
        self.assertIn("_pyn_support.parameter_value(repr(_pyn_param_0), '3', ", generated)
        self.assertIn(""", "'abcd'", """, generated)
        self.assertEqual(generated.count("_pyn_support.parameter_value("), 8, generated)

    def test_a_changed_constant_stops_the_run(self):
        # pytest names the case after the value the test module imported: the conftest's.
        files = dict(CONSTANTS)
        files["tests/conftest.py"] = "import pkg\n\npkg.ALPHABET = 'zzzzzz'\n"
        files["tests/test_ids.py"] = ("import pytest\nfrom pkg import ALPHABET\n\n\n"
                                      "@pytest.mark.parametrize('size', [len(ALPHABET), 9])\n"
                                      "def test_sizes(size):\n    assert size >= 3\n")
        status, output, error, report = self.run_python(files, str(self.root / "tests"))
        self.assertEqual(status, 2, output + error)
        self.assertEqual(report["results"][0]["state"], "execution-error")
        self.assertIn("parameter len(ALPHABET) is 6 where the collector read 3 from the sources", output + error)

    def test_only_one_literal_binding_is_read(self):
        table = {
            "TWICE": "value0",  # (bound twice)
            "MADE": "value0",   # (a call's value)
            "KEPT": "value0",   # (a function rebinds it)
            "NAMES": "value0",  # (a list: pytest names it by position)
            "RATIO": "0.5",
        }
        files = dict(CONSTANTS)
        del files["tests/test_ids.py"]
        for index, name in enumerate(table):
            files[f"tests/test_{index}.py"] = (f"import pytest\nfrom pkg.constants import {name}\n\n\n"
                                               f"@pytest.mark.parametrize('value', [{name}])\n"
                                               "def test_value(value):\n    assert value\n")
        # A second binding in the test module, and a rebinding in one of its functions.
        files["tests/test_twice.py"] = ("import pytest\nfrom pkg.constants import RATIO\n"
                                        "from pkg import LIMIT as RATIO\n\n\n"
                                        "@pytest.mark.parametrize('value', [RATIO + 1])\n"
                                        "def test_value(value):\n    assert value\n")
        files["tests/test_global.py"] = ("import pytest\nfrom pkg.constants import RATIO\n\n\n"
                                         "def change():\n    global RATIO\n    RATIO = 3\n\n\n"
                                         "@pytest.mark.parametrize('value', [RATIO + 1])\n"
                                         "def test_value(value):\n    assert value\n")
        # ids= names the case: the program has no value to check.
        files["tests/test_named.py"] = ("import pytest\nfrom pkg.constants import RATIO\n\n\n"
                                        "@pytest.mark.parametrize('value', [RATIO], ids=['half'])\n"
                                        "def test_value(value):\n    assert value\n")
        paths = self.files(files)
        results = runner.run_suite(paths, self.root, self.work, "python", [], sys.executable, 60)
        ids = {result.path: [case.split("[", 1)[1][:-1] for case in result.cases] for result in results}
        expected = {f"tests/test_{index}.py": [label] for index, label in enumerate(table.values())}
        expected.update({"tests/test_twice.py": ["value0"], "tests/test_global.py": ["value0"],
                         "tests/test_named.py": ["half"]})
        self.assertEqual(ids, expected)
        self.assertEqual({result.state for result in results}, {"passed"}, [result.error for result in results])
        generated = {path.name: path.read_text() for path in self.work.rglob("test_*.py")}
        self.assertEqual([name for name, text in sorted(generated.items()) if "parameter_value(" in text],
                         ["test_4.py"])

    @unittest.skipUnless(NATIVE, "native compiler opt-in required")
    def test_native_jit_and_aot_check_the_values(self):
        paths = [path for path in self.files(CONSTANTS) if path.name.startswith("test_")]
        for mode in ("jit", "aot"):
            with self.subTest(mode=mode):
                results = runner.run_suite(paths, self.root, self.work / mode, mode, shlex.split(NATIVE),
                                           sys.executable, 300)
                expected = runner.oracle(paths, self.root, self.work / "oracle", sys.executable, 120)
                self.assertEqual(runner.compare(results, expected), [], results[0].error + results[0].stderr)
                self.assertEqual([case.split("::", 1)[1] for case in results[0].cases], CONSTANT_IDS)


class StyleRejections(TemporarySuite):
    def test_unsupported_forms_are_collection_errors(self):
        unit = "import unittest\nimport pytest\nclass Case(unittest.TestCase):\n"
        forms = {
            "setUpClass": (unit + "    @classmethod\n    def setUpClass(cls): pass\n", "method: setUpClass"),
            "addCleanup": (unit + "    def test_a(self):\n        self.addCleanup(print)\n", "use: addCleanup"),
            "test id": (unit + "    def test_a(self):\n        print(self.id())\n", "use: id"),
            "setUp call": (unit + "    def setUp(self): pass\n    def test_a(self):\n        self.setUp()\n", "use: setUp"),
            "subTest name": (unit + "    def test_a(self):\n        with self.subTest() as sub:\n            pass\n",
                             "subTest is supported as"),
            "subTest call": (unit + "    def test_a(self):\n        with self.subTest(n=len('a')):\n            pass\n",
                             "subTest arguments"),
            "assertRaises value": (unit + "    def test_a(self):\n        x = self.assertRaises(ValueError, int, 'x')\n",
                                   "callable form of assertRaises"),
            "assertRaises keyword": (unit + "    def test_a(self):\n        with self.assertRaises(ValueError, foo=1):\n"
                                     "            pass\n", "assertRaises supports"),
            "assertWarns value": (unit + "    def test_a(self):\n        self.assertWarns(UserWarning, print)\n",
                                  "assertWarns is supported as"),
            "fixture": (unit + "    @pytest.fixture\n    def value(self): return 1\n", "fixtures defined in a unittest"),
            "arguments": (unit + "    def test_a(self, value): pass\n", "take no arguments"),
            "parametrize": (unit + "    @pytest.mark.parametrize('n', [1])\n    def test_a(self): pass\n",
                            "cannot be parametrized"),
            "pytest xfail": (unit + "    @pytest.mark.xfail\n    def test_a(self): pass\n", "use unittest.expectedFailure"),
            "skip arguments": (unit + "    @unittest.skipIf(True)\n    def test_a(self): pass\n", "a condition and a reason"),
            "__init__": (unit + "    def __init__(self): pass\n", "method: __init__"),
            "setup_method": (unit + "    def setup_method(self): pass\n", "method: setup_method"),
            "mock": ("from unittest import mock\n", "unsupported unittest import: mock"),
            "unittest.mock": ("import unittest.mock\n", "unsupported unittest import"),
            "unittest call": ("import unittest\nunittest.main()\n", "unsupported unittest use: unittest.main"),
            "decorator on a function": ("import unittest\n@unittest.skip('x')\ndef test_a(): pass\n",
                                        "unittest decorators are supported"),
            "nested case": ("import unittest\nif True:\n    class Case(unittest.TestCase):\n        pass\n",
                            "nested and conditional"),
            "table from a call": ("import pytest\ndef cases(): return [1]\n@pytest.mark.parametrize('n', cases())\n"
                                  "def test_a(n): pass\n", "a table the collector can read"),
            "table bound twice": ("import pytest\nCASES = [1]\nCASES = [2]\n@pytest.mark.parametrize('n', CASES)\n"
                                  "def test_a(n): pass\n", "one literal binding: CASES"),
            "table of a set": ("import pytest\n@pytest.mark.parametrize('n', {1, 2})\ndef test_a(n): pass\n",
                               "a table the collector can read"),
            "empty range": ("import pytest\n@pytest.mark.parametrize('n', range(0))\ndef test_a(n): pass\n",
                            "nonempty table"),
            "ids of objects": ("import pytest\n@pytest.mark.parametrize('n', [1], ids=[object()])\ndef test_a(n): pass\n",
                               "literal"),
            "warns value": ("import pytest\ndef test_a():\n    record = pytest.warns(UserWarning)\n",
                            "one context of a with"),
            "warns with raises": ("import pytest\ndef test_a():\n    with pytest.warns(UserWarning), "
                                  "pytest.raises(ValueError):\n        pass\n", "one context of a with"),
            "warns keyword": ("import pytest\ndef test_a():\n    with pytest.warns(UserWarning, other=1):\n        pass\n",
                              "match= only"),
            "raises callable value": ("import pytest\ndef test_a():\n    print(pytest.raises(ValueError, int, 'x'))\n",
                                      "statement of its own"),
            "relative import": ("from . import helpers\ndef test_a(): pass\n", "to be a package"),
            "hook": ("def pytest_collection_modifyitems(items): pass\n", "unsupported pytest hook"),
            "self-requesting override": ("import pytest\n@pytest.fixture\ndef tmp_path(tmp_path): return tmp_path\n",
                                         "requests the fixture it overrides"),
        }
        for name, (source, message) in forms.items():
            with self.subTest(form=name), self.assertRaisesRegex(CollectionError, message):
                generate(source, "test_suite.py")
        # A report-only hook is dropped from a conftest.py, whatever its body does.
        module, _ = generate_conftest("def pytest_report_header(config):\n    return str(eval('1'))\nVALUE = 1\n",
                                      "conftest.py")
        self.assertNotIn("pytest_report_header", module.source)
        self.assertEqual(module.hooks, [])
        # A session or collection hook is left out only while pytest's own run is compared.
        hooks = "def pytest_addoption(parser): pass\ndef pytest_collection_modifyitems(items): pass\n"
        with self.assertRaisesRegex(CollectionError, "pytest_addoption is not run natively"):
            generate_conftest(hooks, "conftest.py")
        module, _ = generate_conftest(hooks, "conftest.py", verified=True)
        self.assertNotIn("def pytest_", module.source)
        self.assertEqual(module.hooks, ["pytest_addoption", "pytest_collection_modifyitems"])
        # So is a fixture that only fills the namespace of doctests, which the program does not run.
        doctest = ("import pytest\n@pytest.fixture(autouse=True)\ndef names(doctest_namespace):\n"
                   "    doctest_namespace['os'] = __import__('os')\n@pytest.fixture\ndef kept():\n    return 1\n")
        with self.assertRaisesRegex(CollectionError, "names is not run natively"):
            generate_conftest(doctest, "conftest.py")
        module, exported = generate_conftest(doctest, "conftest.py", verified=True)
        self.assertNotIn("doctest_namespace", module.source)
        self.assertEqual((module.hooks, list(exported)), (["names (doctest_namespace)"], ["kept"]))
        # And a change of sys.path: the program's imports are resolved when it is built.
        paths = "import sys\nsys.path.insert(0, '.')\nVALUE = 1\n"
        with self.assertRaisesRegex(CollectionError, "sys.path changes are not made natively"):
            generate_conftest(paths, "conftest.py")
        module, _ = generate_conftest(paths, "conftest.py", verified=True)
        self.assertNotIn("sys.path", module.source)
        self.assertEqual(module.hooks, ["sys.path.insert(0, '.')"])
        for source, message in (
                ("def pytest_generate_tests(metafunc): pass\n", "unsupported pytest hook: pytest_generate_tests"),
                ("def pytest_configure(config): pass\nHOOK = pytest_configure\n", "is used by other code")):
            with self.subTest(source=source), self.assertRaisesRegex(CollectionError, message):
                generate_conftest(source, "conftest.py", verified=True)

    def test_layouts_pytest_cannot_import_are_rejected(self):
        first = self.source("def test_a(): pass\n", "a/test_same.py")
        second = self.source("def test_b(): pass\n", "b/test_same.py")
        with self.assertRaisesRegex(CollectionError, "two test modules would be imported as test_same"):
            runner.layout([first, second], self.root)
        # As packages they have different names.
        self.source("", "a/__init__.py")
        self.source("", "b/__init__.py")
        self.assertEqual(list(runner.layout([first, second], self.root).modules.values()),
                         ["a.test_same", "b.test_same"])
        self.source("", "__init__.py")
        with self.assertRaisesRegex(CollectionError, "--root is inside a package"):
            runner.layout([first], self.root)

    def test_imported_base_class_limits(self):
        self.source("", "tests/__init__.py")
        self.source("""
            import unittest
            class Decorated(unittest.TestCase):
                @unittest.skip("x")
                def test_a(self): pass
            class Plain(unittest.TestCase):
                def check(self): pass
        """, "tests/base.py")
        cases = {
            "from .base import Decorated\nclass Mine(Decorated):\n    pass\n": "decorated methods of an imported base",
            "from .base import Plain\nclass Mine(Plain):\n    def test_a(self):\n        self.check()\n": "",
            "from library import Other\nclass TestMine(Other):\n    def test_a(self): pass\n":
                "imported or computed base classes",
            # pytest collects an imported unittest case where it is imported: its limits apply there too.
            "from .base import Decorated\ndef test_a(): pass\n": "decorated methods of an imported base",
            # A decorated class that no test derives from is only a value of the module.
            "from .records import Record\ndef test_a():\n    assert Record(1).value == 1\n": "",
        }
        self.source("from dataclasses import dataclass\n@dataclass\nclass Record:\n    value: int\n",
                    "tests/records.py")
        for index, (source, message) in enumerate(cases.items()):
            path = self.source(source, f"tests/test_{index}.py")
            result = runner.run_suite([path], self.root, self.work, "python", [], sys.executable, 60)[0]
            with self.subTest(source=source):
                if message:
                    # The class or the import the limit rejects is left out, with the limit as its reason.
                    # (The module "library" exists nowhere: its import fails the run that is left.)
                    self.assertIn(result.state, ("empty", "passed", "execution-error"), result.error)
                    self.assertIn(message, " ".join([*result.uncollected.values(), *result.unbound.values()]))
                else:
                    self.assertEqual(result.state, "passed", result.error + result.stderr)
                    self.assertEqual((result.uncollected, result.unbound), ({}, {}))


class HelperModules(unittest.TestCase):
    def test_modules_that_need_nothing_are_unchanged(self):
        source = "# a comment\nVALUE = 1\n\n\ndef twice(n: int) -> int:\n    return n * 2\n"
        self.assertEqual(adapt_helper(source, "helpers.py"), source)

    def test_helpers_are_adapted_without_being_collected(self):
        adapted = adapt_helper(textwrap.dedent("""
            # pystachy: any
            import os
            import unittest
            import pytest
            HERE = os.path.dirname(__file__)
            class Base(unittest.TestCase):
                def setUp(self):
                    super().setUp()
                    self.value = 1
                def check(self):
                    with self.subTest(value=self.value):
                        self.assertIsInstance(self.value, int)
            @pytest.fixture
            def unused():
                return 1
            if __name__ == "__main__":
                unittest.main()
        """), "tests/base.py", "/project/tests/base.py", "tests.base")
        self.assertIn("# pystachy: any", adapted)
        self.assertIn("import pytest_native_support as unittest", adapted)
        self.assertIn("HERE = os.path.dirname('/project/tests/base.py')", adapted)
        self.assertIn("def __init__(self):\n        super().__init__()\n        self.value = 1", adapted)
        self.assertIn("with self.subTest():", adapted)
        self.assertIn("self.assertTrue(isinstance(self.value, int))", adapted)
        self.assertNotIn("@pytest.fixture", adapted)
        self.assertNotIn("unittest.main", adapted)
        compile(adapted, "base.py", "exec")


if __name__ == "__main__":
    unittest.main()
