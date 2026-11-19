# Native tests with adapted pytest syntax

`tools/pytest_native.py` is an experimental, hosted collector for a bounded pytest
source dialect. It generates ordinary typed Python, then runs the test bodies,
fixtures and application code under Pystachy. It does not compile the pytest
package or load its plugins. The compiler and its default type/performance policy
are unchanged.

## Run a suite

Use the development environment from [installation](install.md), including the
pinned pytest in `tools/requirements-dev.txt`, and a working LLVM toolchain. Build
the native compiler with `make` first: it reuses the native program cache, so an
unchanged JIT rerun skips compilation, while the default hosted compiler compiles
every run again.

```sh
python3 tools/pytest_native.py path/to/tests --compiler ./pystachy
python3 tools/pytest_native.py path/to/tests/test_api.py::test_parse --compiler ./pystachy
python3 tools/pytest_native.py path/to/tests --mode aot --compiler ./pystachy --json build/test-results.json
```

Node IDs (`path::test`, `path::test[id]`, `path::TestClass` or
`path::TestClass::test`) select cases as pytest's arguments do: in the order given,
and an unknown ID is an error. As in pytest, an ID that another one contains is
dropped: `path::test` covers `path::test[id]`, and a class covers its tests. Give
node IDs for every argument, with one module's IDs together. The module is still
imported whole. The real pytest oracle runs the same selection.

`-k EXPRESSION` and `-m EXPRESSION` then keep the cases that match, as pytest's
options do: names joined by `and`, `or` and `not`, with parentheses. `-k` looks for
each name, in any letter case, inside the test's name and ID, its class, module and
directories, and its marks; `-m` matches the marks themselves (`slow`, `skip`,
`parametrize` and so on). The collector decides this from the source, so a mark that
a `conftest.py` hook or a plugin adds at run time is not seen: the comparison then
reports the cases pytest selected and the program did not.

```sh
python3 tools/pytest_native.py tests -k "parse and not slow" --compiler ./pystachy
python3 tools/pytest_native.py tests -m "not network" --compiler ./pystachy
```

Oracle comparison is enabled by default; `--compare` also selects it explicitly.
It runs the **original** files in real CPython pytest, independently of
the transformed programs. It compares collected test IDs/order and every
setup/call/teardown outcome. It does not claim exact traceback, warning, failure
message or captured-output parity. Both executions must have equivalent external
inputs; tests which modify persistent external state need their own isolation.

Use `--no-compare` only for repeated runs of previously qualified, unchanged inputs.
The CLI prints `UNVERIFIED` and records `"qualification": "unverified"` in JSON
when the oracle is disabled. Static collection cannot identify pytest behavior
hidden in imported objects, such as an imported autouse fixture. Default comparison
turns these omissions into errors; disabling it removes that check. The direct
execution timings below and in the benchmark are measured **after** oracle
qualification, without repeating comparison inside every timed execution.

`--mode python` runs generated code under CPython and is useful for distinguishing
collector/helper mistakes from native compiler behavior. `--compiler './pystachy'`
selects a bootstrapped compiler; the default is the hosted compiler in this
checkout. A relative compiler path is resolved where the command is given, although
the compiler runs from `--root`. `--python` selects the oracle interpreter; a
missing pytest is reported as such. `--timeout` bounds each build/run/oracle
subprocess.

Each failure shows the native exception's class and message (`KeyError: 'missing'`),
as pytest's summary does. A comparison assertion with no message (`==`, `!=`, `<`,
`<=`, `>`, `>=`, `in`, `not in`) also shows its operands' `repr()`s, such as
`assert 4 == 5`. Names are read again for this; other operands are kept in reserved
temporaries as they are evaluated, once and in order. When the original pytest also
fails, its own report follows. A case or phase whose outcome differs from pytest's
is listed as `MISMATCH`, and a summary line counts the outcomes. If the native
compiler rejects the operand code (for example, `repr()` of a function), the program
was never started, and the suite is built again with plain assertion messages; the
JSON keeps that build's error, and later runs of the unchanged code skip it. An
operand whose `__repr__` raises is shown as such, and the assertion still fails as
an `AssertionError`.

The compiler reads generated modules. Its diagnostics name the test's own line
first and the generated one after it:
`tests/test_api.py:13 [generated test_api.py:20]: error: ...`. Code that the runner
generates for a declaration (a case's fixture calls, a scope's cache, parameter
values) reports at that test, fixture or class.

A test that the collector or the compiler rejects does not stop the others. Suites
often have a few: a test under a hypothesis or `mock.patch` decorator, or with a
parameter table made at run time, which the collector cannot preserve; a test that
passes a `str` where the code under test declares an `int`, or omits an argument, to
see its `TypeError`, which is a type error to a compiler. The runner leaves such a
test out of the program, which is then the one its file would make without that
test: nothing of it runs, its decorators included.

- **Tests the collector rejects.** The collector names the line it rejects. A test
  function or method with that line is left out, and a class when the line is in it
  but in none of its tests; classes that derive from one left out go with it. Each
  is printed as `NOT COLLECTED` with the reason and listed in the JSON's
  `uncollected`.
- **Tests the compiler rejects.** The compiler's diagnostic names the rejected line
  and the calls that led to it; the first of them in a test blames it. That test is
  left out with every parametrized case it has and the program is built again, up
  to 25 times for a suite. Each case is printed as `NOT COMPILED` with the
  diagnostic and listed in `uncompiled`. No test runs twice: a program whose build
  fails has not started.
- **Fixtures.** A fixture of a test module or a `conftest.py` that either rejects is
  left out, unless it is autouse, and the tests that request it, directly or
  through another fixture, are left out for it. No other fixture of its name takes
  its place: not a wider `conftest.py`'s, not pytest's own. A nearer `conftest.py`
  that defines the name provides it again, as in pytest. The fixture is printed as
  `NOT AVAILABLE` and listed in `unavailable`.
- **Imports and assignments.** A module-level statement of a test module or a
  `conftest.py` that only binds names and that either rejects is left out:
  `from unittest import mock`, `import pickle` for a module Pystachy does not have,
  the one name of `from functools import reduce, total_ordering` that its module
  lacks, or a mark kept in a name the collector cannot read. What uses the name is
  then rejected for it: a test is left out in its turn, and anything else fails as
  before. The statement is printed as `NOT BOUND` and listed in `unbound`. A name
  pytest reads by itself stays: `pytestmark`, `pytest_plugins`, `collect_ignore`.

```text
tests/test_api.py: passed (41 cases, 3 not compiled, 2 tests not collected)
NOT COLLECTED tests/test_api.py::test_round_trip
    tests/test_api.py:20: unsupported test decorator
NOT COMPILED tests/test_api.py::test_rejects_text[one]
    tests/test_api.py:31 [generated test_api.py:19]: error: expected int, got str
```

Such a run exits with 2, never 0: pytest ran tests, or a statement, that the program
does not have. Its `qualification` is `partial` when everything the program has
matches pytest; each case pytest ran of a test left out is a `MISMATCH` line with
pytest's outcome, and so is a test that needed the side effects of something left
out. What is rejected elsewhere still rejects the module or fails the build: a
module's other statements, star imports, an autouse fixture, a `conftest.py`'s
hooks, a helper that no call leads to from a test, or the package under test. So
does a test named by a node ID.

`--root` defaults to the current directory, and selected files must be inside it.
Tests may be in several directories and in packages. The generated program mirrors
how pytest imports them: a module of a package (a directory with `__init__.py`)
under its dotted name, from a copy of the package in the work directory, and any
other module under its file's name. Relative imports therefore resolve as they do
under pytest. The package's other modules are copied with it, and a module beside
the tests that needs it is [adapted](#modules-beside-the-tests). Two test
directories that are not packages cannot each have a module of one name: pytest
gives every test its own directory's, where a compiled program has one.

Each `conftest.py` from `--root` down to a test supplies fixtures to the tests of
its directory and below, an outer directory's autouse fixtures first; a nearer
file's fixture replaces an outer one of its name. All selected modules are
collected before execution, imported before tests run, and executed in one process,
preserving shared imported-module state. Empty test modules are imported too: an
import failure cannot disappear from the result. Generated modules keep their test
modules' names, so `__module__` and `repr()` of their classes and functions match,
and `__file__` and `__name__` read as the original module's. A module that cannot
be collected is reported without running the pytest oracle.

The runner reads the configuration pytest would use: the first of `pytest.toml`,
`pytest.ini`, `pyproject.toml` (`[tool.pytest.ini_options]` or `[tool.pytest]`),
`tox.ini` and `setup.cfg` from the tests' directory up to `--root`. None of it is
silently ignored. Options that only shape pytest's report are accepted (`testpaths`,
`minversion`, `log_*`, `junit_*`, and in `addopts` flags such as `-ra`, `-q`,
`--tb=short`, `--color`). `xfail_strict`, `pythonpath`, `markers` with
`--strict-markers`, `-k` and `-m` in `addopts` (the command line's replace them),
and `filterwarnings` or `-W` entries made of an action, a message and a built-in
warning class are honored, in the program and in the comparison's pytest alike. Any
other option is an error that names it: `-x`, `-n`, coverage and other plugins'
options, changed `python_files`, `python_classes` or `python_functions`, and filters
on a project's own warning class.

Generated sources, executables and phase reports live in `--work-dir` (default
`build/pytest-native`). The CLI locks that directory against concurrent runs;
parallel independent suites need different work directories. Stable generated
paths permit Pystachy's existing JIT program cache to reuse valid programs.
AOT mode builds once for the selected suite per invocation. JSON timing/output
fields on the first module describe the whole suite, not that module alone.
This hosted tool currently targets Linux and macOS.

## Supported source forms

- Module-level functions with the default pytest `test` prefix; ordinary helper
  functions/classes and supported application imports remain in the program.
  A literal named like a test (`test_cases = [...]`), `import test_helpers`, and a
  `test*` function nested in another function or in an ordinary class are not tests
  for pytest either.
- Test classes: `class TestX:` at module level, without `__init__` or nested test
  classes. Each test method runs on a new instance; helper methods and class
  attributes stay. Marks on the class (`skip`, `skipif`, `xfail`, `parametrize`,
  `usefixtures`, labels) apply to its tests after each method's own. A class may
  define function-scoped fixtures as methods, which share the test's instance.
  Declarations inside a class are evaluated before its body: they cannot use the
  class's own attributes, and a `skipif` expression there is limited to names,
  attributes, literals and comparisons.
- One base class per test class, defined in the module or imported: from a module
  beside the tests, or from the source tree where `--root` or a configured
  `pythonpath` directory makes it importable (`from package.testing import Base`).
  It may be named `Base` or `module.Base`. The class runs the tests and fixtures it
  inherits, a base's tests first, as pytest orders them; marks of a base class apply
  too. A base that is not named `Test*` is not collected itself. An imported base's
  test methods must be undecorated. `Generic[T]`, `abc.ABC` and `object` beside the
  base only type the class.
- pytest collects no `Test*` class that has a constructor, and neither does the
  runner where the constructor is inherited, a `Protocol`'s included. A `Test*`
  class that defines `__init__` itself is rejected.
- An imported class named `Test*` that has no constructor is collected in the
  importing module, under the name bound there, as an imported `unittest.TestCase`
  is under any name. An imported module, a class with a constructor and a function
  named `Test*` are not tests. An imported name that begins `test` or `Test` and
  that the collector cannot read, such as a test function or a class of an
  installed package, is rejected.
- `setup_method` and `teardown_method`, with or without their `method` argument
  (which may only be passed to `super()`). They run where pytest runs them: after
  wider fixtures and the module's and `conftest.py`'s autouse fixtures, before the
  class's own. The compiler requires that `__init__` declares instance attributes,
  so the runner makes `setup_method` the class's `__init__`: attributes it assigns
  are declared, while state first assigned in a method fixture
  (`self.client = ...`) still runs under CPython only. `setup_class`,
  `teardown_class` and the module-level hooks are rejected.
- `unittest.TestCase` classes, whatever their names, with `setUp`, `tearDown`,
  inherited tests in unittest's sorted order, `self.subTest()`, `skipTest`,
  `@unittest.skip`, `skipIf`, `skipUnless` and `expectedFailure`. As under pytest,
  `setUp`, the test and `tearDown` run in the call phase; a second failure is
  reported as the teardown's, and each `subTest` block reports apart from its test;
  an `expectedFailure` test ends at its first failing `subTest`, the failure it expects.
  A `subTest`'s message and parameters only label its report, but are evaluated where
  the block is entered; a block whose nested `subTest` failed reports no success.
  `assertRaises` without the exception fails with an `AssertionError`, as unittest's does.
  `setUp` becomes `__init__` here too. Assertions: `assertEqual`, `NotEqual`,
  `True`, `False`, `Is`, `IsNot`, `IsNone`, `IsNotNone`, `In`, `NotIn`,
  `IsInstance`, `NotIsInstance`, `Greater`, `GreaterEqual`, `Less`, `LessEqual`,
  `AlmostEqual`, `NotAlmostEqual`, `Regex`, `NotRegex`, `CountEqual`,
  `SequenceEqual`, the `List`/`Tuple`/`Set`/`Dict`/`MultiLine` forms, `fail`,
  `assertRaises` and `assertRaisesRegex` (context and callable forms, with
  `cm.exception`), `assertWarns` and `assertWarnsRegex`. `setUpClass`,
  `addCleanup`, `assertLogs`, `self.id()`, `unittest.mock` and fixtures defined in
  a case are rejected. A helper base case in a module beside the tests is adapted
  with them.
- Plain `assert`, with a source location and expression added when no message
  exists. Assertion expressions retain their evaluation order and execute once.
- `@pytest.mark.parametrize` with stacked parametrization and `ids=` lists of
  strings, numbers or `None`. A value may be any expression; it is evaluated once
  where the decorator stands. Its ID is pytest's: the value of a literal, the name
  of a class or function, and the argument's name and index for another object.
  Only syntax is read, so an ID of a value that a call computes (a string that
  `make()` returns) is not known: give `ids=`, or the comparison reports it.
  A value computed from a constant of a module beside the tests is read too, such
  as `len(ALPHABET) + 1` after `from package.constants import ALPHABET`: the
  constant is the one module-level number, string, bytes or `None` literal that
  its module binds to the name. The program checks the value where it binds the
  parameter and stops a run in which another module has changed it.
- Tables the collector can read without running test code: a list or tuple,
  `range()`, comprehensions over literals, `+`, `*`, slices, f-strings,
  `sorted()`, `zip()`, `enumerate()`, `itertools.product()` and similar pure calls,
  a dict's `items()`, and a name bound once to any of these. A named list or tuple
  is read after the module's import, as pytest reads it when it collects, so its
  rows are the module's own objects; the program checks the table's length against
  the source's. A table that a function call or a file makes is rejected.
- Inline `pytest.param(..., id="case", marks=...)` entries with static
  skip/skipif/xfail marks. A named table cannot hold `pytest.param` rows.
- Return/yield fixtures defined in the selected module, in a test class or in a
  `conftest.py` above the test, with dependencies and literal `autouse`. A fixture
  replaces a `conftest.py` one of its name unless it requests that fixture itself.
  `@pytest.fixture(name="alias")` exposes an explicit public fixture name.
  Repeated requests share one fixture value within a test. Teardown resumes yield
  fixtures in reverse setup order, including after a test fails or later fixture
  setup fails; one cleanup failure does not discard the remaining cleanup.
- Fixture scopes `function`, `class`, `module` and `session` for module-level and
  `conftest.py` fixtures. A wider fixture is set up at its first request and torn
  down in the teardown of the last case of its class, module or run, innermost
  scope first, including when that case is skipped. A setup failure or skip is
  kept and repeated for every later request in the scope without running the
  fixture again. A class-scoped fixture ends with each test outside a class, as in
  pytest. Fixtures cannot request a narrower scope. The runner caches a wider
  fixture's value in a list typed from its return annotation (`T`, or
  `Iterator[T]` for a yield fixture) where it has one; annotate a fixture whose
  value's type the compiler cannot infer, such as an empty container.
- `@pytest.fixture(params=[...], ids=[...])` on function-scoped fixtures, read as
  `request.param`. Cases and IDs follow pytest: fixture parameters in the order of
  the test's fixture closure, then its `parametrize` marks; a directly parametrized
  argument replaces a fixture of that name. A fixture may also name `request` and
  never read it. Other uses of `request`, parametrized wider scopes (pytest reorders
  tests around them) and `indirect=` are rejected.
- Built-in `tmp_path` (a new empty `pathlib.Path` directory per test, named as
  pytest names it and removed after the run), `tmp_path_factory` (`mktemp()`,
  numbered as pytest numbers it, and `getbasetemp()`), and `tmpdir` with the part
  of `py.path.local` that tests of temporary files use: `join`, `mkdir`, `ensure`,
  `write`, `read`, `check`, `exists`, `isdir`, `isfile`, `listdir`, `remove`,
  `basename`, `dirname`, `strpath`, `/` and `str()`.
- `recwarn`: the warnings raised since its setup, with `len()`, indexing,
  iteration, `.list`, `.pop(Class)` and `.clear()`.
- `caplog`: `records`, `record_tuples`, `messages`, `text`, `clear()`,
  `set_level()` and `at_level()`, through one handler on the root logger. It
  records from the fixture's setup to its teardown, where pytest starts a new list
  for each phase of a test.
- `capsys` and `capfd`: `readouterr()`, as a pair or by `.out` and `.err`, and
  `disabled()`. Both redirect descriptors 1 and 2 to files, as pytest's `capfd`
  does: a compiled `print()` writes to descriptor 1 whatever `sys.stdout` names.
  They need a compiler that has `os.dup`, `os.dup2` and `os.close`; on an older
  one a test that requests them fails to compile.
- `monkeypatch`: `setenv`, `delenv`, `undo`, `context()`, and `setattr(target,
  "name", value)`, `setitem(mapping, key, value)`, `delitem(mapping, key)` and
  `chdir(path)` as statements of their own. The last four are written out where the
  test calls them, typed by their arguments. They patch data: a field of an
  object, a variable of a module, an item of a dict. A compiled call reaches the
  function it names, so replacing a function or a method is a compile error, as is
  an attribute the object does not have. `setattr` with a dotted name or
  `raising=False`, `delattr` and `syspath_prepend` are rejected.
  `chdir` needs a compiler that has `os.chdir`.
- `pytest.raises(ExceptionClass, match="regex")` and a literal tuple
  `pytest.raises((A, B))` as a context manager, with `.value`, `.type`,
  `.typename` and `.match(regex)`. The callable form
  `pytest.raises(E, function, *arguments)` is written out as that block where it
  is a statement of its own or assigned to a name; the function is looked up on
  its object and the arguments are evaluated first, in that order, as pytest
  evaluates them. `check=` and compiled regexes are outside this
  subset. The context holds a `BaseException`, whose own
  fields compiled code cannot read. Where a function reads
  `info.value.attribute`, its `with pytest.raises(E) as info:` block is expanded
  to `try`/`except E`, so `info.value` has class `E`. This needs one class that
  the function does not bind itself, a name bound by one block only and used as
  `.value`, `.type`, `.typename` or `.match(...)`, and no `return`, `break` or
  `continue` in the block; otherwise the context manager stays, and reading such
  a field is a compile error.
- `with pytest.warns(Category, match="regex") as record:`, a literal tuple of
  categories, `pytest.warns()` and `pytest.deprecated_call()`, as the one context
  of a `with` statement. The block runs inside `warnings.catch_warnings`; `record`
  is its list of warnings. As in pytest, a block that raises an `Exception` without
  the warning fails for the missing warning. Unmatched warnings are not emitted
  again afterwards.
- `actual == pytest.approx(expected, rel=..., abs=..., nan_ok=...)` and `!=` for
  `int` and `float`, with pytest's tolerances. Write `pytest.approx(...)` directly
  in the comparison, or on its left: a number does not consult a stored approx
  object in compiled code. Sequences, mappings and other types are unsupported.
- `pytest.fail`, `pytest.skip`, `pytest.xfail`, and static skip/skipif/xfail marks,
  including strict XPASS, `run=False` and `raises=` with a class or a literal tuple
  of classes. Boolean conditional markers require an explicit reason, as in pinned
  pytest.
- A test decorator's `skipif` condition may be an expression, such as
  `sys.platform == "win32"`: it is evaluated once at import, in decorator order, as
  pytest's decorator is. String conditions, which pytest evaluates as code, and
  conditions inside `pytest.param` remain literal-only.
- `@pytest.mark.usefixtures("name", ...)` with literal names, set up after autouse
  fixtures and before argument fixtures, nearest decorator first, as pytest does.
- Marks that only label tests, such as `@pytest.mark.slow`, with literal arguments.
  The isolated oracle loads no plugin that gives them meaning; `-m` and `-k` select
  by them. Other marks with behavior are rejected.
- `@pytest.mark.filterwarnings("action:message:category")` with a built-in warning
  class, on a test, a class or in `pytestmark`. The filters apply around the test's
  setup, call and teardown, over the configuration's, in pytest's order: of two
  marks that match one warning, the one further from the function wins. An `ignore`
  of one of pytest's own warning classes is accepted and does nothing.
- A module-level name for a mark, assigned once: `slow = pytest.mark.slow`,
  `needs_posix = pytest.mark.skipif(sys.platform == "win32", reason="...")`,
  `cases = pytest.mark.parametrize("n", [1, 2])`, and `parametrize =
  pytest.mark.parametrize` or `mark = pytest.mark`. The mark is read where the name
  is assigned. Names for marks in a `conftest.py` or imported from another module
  are rejected.
- `pytestmark = mark` or a list of marks, in a module or a test class, applied
  after the marks of each test and of its class.
- `if __name__ == "__main__":` blocks without `else`, which never run in a module
  that pytest imports, are left out. Elsewhere `__name__` is the test module's
  name and `__file__` its original path: the compiler supports neither itself.
- In a `conftest.py`, `pytest_report_header` and `pytest_terminal_summary`, which
  only add text to pytest's report, are left out.
- In a `conftest.py`, the hooks pytest runs around the session and its collection:
  `pytest_addoption`, `pytest_configure`, `pytest_unconfigure`,
  `pytest_sessionstart`, `pytest_sessionfinish`, `pytest_collection_modifyitems`,
  `pytest_collection_finish` and `pytest_ignore_collect`. **The program does not run
  them.** pytest does, in the comparison, so a hook that skips, deselects, reorders
  or marks a test that ran shows up as a difference and the run fails (exit 2, with
  a note naming the hooks left out); where no outcome depended on them, the run is
  verified as usual. With `--no-compare` nothing would answer for them, and such a
  `conftest.py` is rejected. Other hooks (`pytest_generate_tests`,
  `pytest_runtest_*`, `pytest_collect_file` and the rest) are always rejected.
- In a `conftest.py`, under the same comparison: a fixture that takes
  `doctest_namespace`, which serves doctests the program does not run, and a
  `sys.path.insert(0, ".")` or `sys.path.append()` statement of literals, because
  the program's imports are resolved when it is built.
- `if TYPE_CHECKING:` imports of pytest's names, `from pytest import MonkeyPatch`
  and `from _pytest.fixtures import SubRequest` and the like, where the names only
  annotate parameters and returns: the runner removes those annotations, and a
  parameter is typed by the value it is given.
- Explicit per-source dynamic `Any` opt-in for supported open payloads. The runner
  itself stores metadata, statuses and exceptions in concrete types.

Unsupported source forms detected by the collector are errors, never implicit skips:
a test with one is [left out and reported](#run-a-suite), which fails the run, and
anywhere else the form rejects its module.
Imported fixtures are unsupported; the default oracle checks their observable
collection and phase effects. The collector rejects test classes with `__init__`,
several base classes or a base class it cannot read, async/generator tests,
class- and module-level xunit hooks, `conftest.py` hooks other than those above,
tests in `conftest.py`, a class fixture named as a module one, pytest
configuration it cannot honor, custom decorators (including `unittest.mock.patch` and hypothesis),
plugins, dynamic test creation and unsupported pytest APIs such as
`pytest.importorskip`, `pytester` and `request.node`. It also rejects
namespace inspection/mutation and assignment to module metadata. A name the
collector read a table, an ID or a mark from must be bound once and not changed by
module-level statements; a change it cannot see is caught by the table-length check
or reported by the pytest comparison as a differing ID.

Some of these are limits of a compiled program, not work left to do:

- `unittest.mock` and patches that replace functions. A mock answers any attribute
  and any call, and a patch redirects calls that the compiler has already bound.
- hypothesis, and other decorators that build a test's arguments while it runs.
- Plugins, `pytest_generate_tests` and the `pytest_runtest_*` hooks: they receive
  pytest's own objects, which the program does not have.
- Namespace inspection: `globals()`, `vars(module)` and `getattr()` by a computed name.

### Modules beside the tests

A module in a test package, or beside tests that are in no package, is not
collected, but the generated program may import it. Where it uses `pytest`,
`unittest` or `__file__`, the program imports an adapted copy: those imports name
the runner's replacement, its `unittest.TestCase` classes are adapted as a test
module's are, pytest decorators are removed, and `__file__` is its original path,
so data files beside it are found. Its fixtures and tests are not collected.
Other modules are used as written. The compiler reports adapted modules by their
generated lines.

A module of the source tree that a test class takes its base class from is treated
the same way, with the rest of its package: the program imports the copies, where
`import unittest` names the runner's replacement.

Tests still obey Pystachy's [language compatibility](language/compatibility.md)
and [dynamic boundary contract](dynamic-any.md). There are no blanket `Any`
conversions, container copies to make boxing work, or CPython execution fallbacks.
An opted-in test can still expand numeric identity tracking through its imports;
concrete annotations alone do not prove absence of that cost.

## Failure and verification contract

Reports contain separate setup, call and teardown events plus a completion
record; a unittest case's `subTest` blocks add `subtest` events between its setup
and call, which the comparison includes, and a failed one fails the run as in
pytest. Missing cases, missing call phases, duplicate events, interrupted runs,
malformed reports and disagreement with process status are execution errors.
Test stdout cannot impersonate the report protocol. Exit codes are 0 for success,
1 for test failures, 2 for collection/build/execution/oracle errors and for tests,
fixtures or statements [left out](#run-a-suite) because the collector or the
compiler rejects them, and 5 for no tests. A matching intentionally failing suite
still returns 1.

```sh
make test-pytest-native
PYTHONPATH=ports PYSTACHY_PATH=ports python3 tools/pytest_native.py \
  examples/pytest_native --mode aot --compare --json build/pytest-native-aot.json
```

The target checks original pytest outcomes, negative controls, fixture lifecycle,
shared module state, native JIT/AOT, GC stress and a mixed `Any` fixture. It runs
inside the existing x86-64 `hosted` CI job on code PRs, main pushes and manual runs.
The examples' JIT run uses the hosted compiler; `PYTEST_NATIVE_COMPILER="$PWD/pystachy"`
gives their AOT build and the runner's own tests and controls a bootstrapped
compiler, as CI does.
The examples exercise current stdlib APIs and the
iniconfig/jdcal/json_repair/roman ports. The 72 cases include 16 JSON-repair cases for
malformed/Unicode input, result objects, logs, fixture aliases and strict errors, 14
for test classes, fixture scopes and parameters, `tmp_path`, `monkeypatch`,
`pytest.approx` and typed `pytest.raises` values, and 23 for `unittest.TestCase`
classes with inherited tests and subtests, `pytestmark` and computed parameter
tables. These are
original tests, not claims of complete upstream suite support. Keep the existing
[943-case JSON-repair replay](../tests/upstream/json_repair/README.md) and extension
checks: this runner adds fixture/collection qualification rather than replacing
those broader API checks.

## Shared application and benchmark suites

```sh
python3 tools/pytest_native_suites.py --list
python3 tools/pytest_native_suites.py --suite byte_bpe --mode python
make test-pytest-workloads
```

The registry runs 19 example suites and the 25 delivered pyperformance workloads
as independent suites, each using the same source under original CPython pytest
and generated native execution. Each suite keeps its sibling imports; shared
fixtures across directories are not implied. Every registered case must execute
and pass: a skip, xfail, empty collection or missing report fails qualification.
The default runs JIT and AOT; `--mode python` checks generation separately.
`--json` retains every per-suite collection and phase comparison.
The pyperformance tests use five separate categories to bound native build
memory and keep the JSON dynamic-`Any` consumer separate from typed workloads.

These are API correctness checks. Existing recorded stdout/stderr, real CLIs,
network/FFI/BLAS ownership, package installation and upstream-reference checks
retain their separate contracts. Pyperf-style timing boundaries, checksums,
source hashes and benchmark sampling remain in the benchmark controllers.
Native pytest run/build times are not benchmark speed measurements.

Fixture aliases and parameter IDs/marks are resolved during collection. For
equivalent unmarked declarations the generated program is unchanged; no compiler
or runtime feature is added. Explicit parameter annotations also provide the
types for fresh hoisted container literals containing empties, retaining their
original mutable identity. The tests and benchmarks remain valid CPython.

## Reusing tests and measuring speed

Compatible tests written for CPython can run natively, including adapted tests
from CPython's library suite. Both the test and the library must fit Pystachy's
supported language/API subset; a faster runner does not make an unported package
compile. The [mypy stubgen parser and mypyc NameGenerator experiments](porting.md#port-one-application-component-at-a-time)
are component prototypes, not full mypy/mypyc ports. Start qualification with those
components, keeping CPython's full integration suites for CLI, C extensions,
plugins, subprocesses and other unported dependencies.
The optional [NameGenerator qualification](../examples/pytest_native_mypyc/README.md)
provides ten original cases against a hash-checked, unchanged upstream module;
run it separately from the default examples.

The [test-method extractor](../tools/cpython_test_methods.py) can generate a pytest
suite from an **explicit selection** of unittest methods:

```sh
python3 tools/cpython_test_methods.py pytest \
  tests/upstream/ports/cpython/Lib/test/test_fnmatch.py build/fnmatch-pytest \
  FnmatchTestCase.test_fnmatch FnmatchTestCase.test_fnmatchcase \
  FnmatchTestCase.test_slow_fnmatch
python3 tools/pytest_native.py build/fnmatch-pytest --mode aot --compare \
  --json build/fnmatch-pytest-results.json
```

The destination must be new, preventing stale tests from entering a later
selection. Generated helper classes stay in a separate module; top-level pytest
tests use function-scoped fixtures, a fresh instance for each test, and teardown
after failed calls. Setup failures do not trigger teardown. `selection.json`
records the source SHA-256, selected methods, unselected extractable methods and
decorator/C-accelerator exclusions. Unknown/skipped selections, duplicates,
unsupported unittest calls, class keywords, and discarded class/module lifecycle
or selected decorators are errors.

This applies the extractor's documented mechanical adaptations; it does not port
`unittest` or `test.support`. Subtests become ordinary statements (stopping at the
first failure), and assertion methods become the extractor's plain assertions.
The runner also collects `unittest.TestCase` classes directly (see the supported
forms); the extractor remains the way to select methods of a suite whose module
needs `test.support` or other unported machinery.
`--compare` checks the **adapted pytest suite** under
real CPython pytest. It does not validate the extraction against original unittest.
Retain the upstream pin, license, source and adaptation review, and run the original
selected unittest methods separately where available. The three fnmatch methods
above are a bounded qualification, not complete fnmatch coverage.

## Qualify original upstream tests

Use the maintained [upstream qualifier](../tools/pytest_native_upstream.py) to run
the original methods before extraction. It executes real unittest in an isolated
CPython process, records the full original inventory, and checks the explicit
method-to-pytest mapping through adapted pytest, generated CPython, native JIT
and native AOT. An original failure, skip, expected failure, missing method or
changed source hash fails qualification. Generated CPython always runs before
the native modes, distinguishing extraction errors from compiler/library gaps.

```sh
# Bundled sources, also checked offline in the x86-64 hosted CI job:
python3 tools/pytest_native_upstream.py --suite fnmatch --suite textwrap \
  --compiler ./pystachy --json build/pytest-upstream-bundled.json

# Explicitly fetch hash-pinned statistics support and mypyc sources once:
python3 tools/pytest_native_upstream.py --fetch --compiler ./pystachy \
  --json build/pytest-upstream-all.json
```

The [selection manifest](../tests/upstream/pytest/manifest.json) pins 3 fnmatch,
6 textwrap, 5 statistics, all 5 upstream mypyc NameGenerator methods, 3 of
mypyc's 11 literal-encoder methods and both methods of mypy's `teststubinfo`. It
records complete inventories of 17, 66, 401, 5, 11 and 2 cases respectively;
statistics includes its original doctests, which remain excluded from the
selected methods.
Sources and licenses are verified before copying them to a fresh import snapshot.
No replacement `test.support` stubs are used. The exact methods, exclusions,
original outcomes, source hashes and every generated phase appear in the JSON
report. See [scope and reproduction](../tests/upstream/pytest/README.md).

JSON repair has a separate source-backed qualifier for **53 cases from 40 test
functions**, including all 21 strict-mode cases in its pinned source module:

```sh
git clone --depth 1 --branch v0.64.8 \
  https://github.com/mangiucugna/json_repair.git build/json-repair-upstream
python3 tools/pytest_native_json_repair.py --upstream build/json-repair-upstream \
  --compiler ./pystachy --json build/pytest-json-upstream.json
```

It first runs the selected original files/functions against the pristine upstream
implementation in real pytest. Test functions and decorators are copied exactly;
the adapter changes public import paths, enables the port's existing dynamic
JSON-value contract, and explicitly annotates one open-mapping helper as
`dict[Any, Any]`. Assertions and helper bodies are unchanged. The
[selection file](../tests/upstream/json_repair/pytest-selection.json) records that
refinement and the current typed-dictionary-to-Any representation limitation.
Adapted pytest and generated CPython/JIT/AOT must match the original case IDs
and phase outcomes. The report inventories all **261 cases in the five selected
source modules**, lists the 208 unselected cases, and records every other upstream
test module as outside this scope. This supplements the existing 943-call API
replay; it does not qualify JSON repair's complete upstream test tree.

## Preserve deliberate failures

```sh
python3 tools/pytest_native_controls.py --compiler ./pystachy \
  --json build/pytest-controls.json
```

The control command succeeds only when its known-failing suite has the exact
independent inventory: 30 cases, 90 setup/call/teardown phases, 14 failed phases
and one expected xfail. Three seeded success/failure pairs each cover mutable
fixture aliases, Unicode, numeric boundaries and exception checks. Other cases
cover cleanup errors, remaining cleanup after two errors, and strict XPASS.
Runtime input supplies the seed offset. Both ordinary pytest and generated
CPython/JIT/AOT must preserve every expected success and failure; two engines
agreeing on an incorrectly passing suite cannot qualify it. The unit tests also
mutate assertions, cleanup, skips and reports to verify these rejection gates.

`make test-pytest-native` includes these controls and the bundled original
fnmatch/textwrap qualification without adding a CI job. The optional
`make test-pytest-upstream PYTEST_UPSTREAM_ARGS=--fetch` and
`make test-pytest-json-upstream JSON_REPAIR_UPSTREAM=PATH` targets run the remaining
source-backed qualifications. Timing measurements are a separate workload.

Keep existing stdlib differential corpus tests, upstream inventories, JIT/AOT,
GC-stress and sanitizer gates. Add this runner for convenient new cases and
selected upstream adaptations; migrate existing tests only after matching their
case inventory, assertions and failure controls. Continue recording outcomes from
pinned CPython, report excluded/unsupported methods explicitly, and preserve the
PSF license for adapted CPython material.

Compiled tests exercise Pystachy and its library implementations. They do not
replace CPython's interpreter, bytecode, extension, reference-counting or frame
tests. Running those natively would change what is being tested.

Measure original pytest, generated CPython and native execution separately. Keep
AOT build/cold JIT time separate from repeated runs, and include tiny suites where
compilation can dominate. A faster repeated native suite does not establish that
the first run is faster, or that pytest itself was accelerated.
