# Native tests with adapted pytest syntax

`tools/pytest_native.py` is an experimental, hosted collector for a bounded pytest
source dialect. It generates ordinary typed Python, then runs the test bodies,
fixtures and application code under Pystachy. It does not compile the pytest
package or load its plugins. The compiler and its default type/performance policy
are unchanged.

## Run a suite

Use the development environment from [installation](install.md), including the
pinned pytest in `tools/requirements-dev.txt`, and a working LLVM toolchain:

```sh
python3 tools/pytest_native.py path/to/tests --mode jit --compare
python3 tools/pytest_native.py path/to/tests --mode aot --compare --json build/test-results.json
```

`--compare` runs the **original** files in real CPython pytest, independently of
the transformed programs. It compares collected test IDs/order and every
setup/call/teardown outcome. It does not claim exact traceback, warning, failure
message or captured-output parity. Both executions must have equivalent external
inputs; tests which modify persistent external state need their own isolation.

`--mode python` runs generated code under CPython and is useful for distinguishing
collector/helper mistakes from native compiler behavior. `--compiler './pystachy'`
selects a bootstrapped compiler; the default is the hosted compiler in this
checkout. `--python` selects the oracle interpreter. `--timeout` bounds each
build/run/oracle subprocess.

`--root` defaults to the current directory. Selected files must be inside it and
must share one source directory. The latter restriction preserves sibling-import
resolution; combining arbitrary directories requires additional import support.
All selected modules are collected before execution, imported before tests run,
and executed in one process, preserving shared imported-module state. Empty test
modules are imported too: an import failure cannot disappear from the result.

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
- Plain `assert`, with a source location and expression added when no message
  exists. Assertion expressions retain their evaluation order and execute once.
- `@pytest.mark.parametrize` with bounded static tables, optional literal string
  IDs and stacked parametrization. Values are evaluated once at module import;
  shared mutable values retain aliases across their cases.
- Function-scoped return/yield fixtures, dependencies and literal `autouse`.
  Repeated requests share one fixture value within a test. Teardown resumes yield
  fixtures in reverse setup order, including after a test fails or later fixture
  setup fails; one cleanup failure does not discard the remaining cleanup.
- `pytest.raises(ExceptionClass, match="regex")` as a context manager, including
  guarded `.value` and `.type`; exception tuples, `check=`, callable form and
  compiled regexes are outside this subset.
- `pytest.fail`, `pytest.skip`, `pytest.xfail`, and static skip/skipif/xfail marks,
  including strict XPASS and `run=False`. Boolean conditional markers require
  an explicit reason, as in pinned pytest.
- Explicit per-source dynamic `Any` opt-in for supported open payloads. The runner
  itself stores metadata, statuses and exceptions in concrete types.

Unsupported collection is an error, never an implicit skip. The collector rejects
test classes, async/generator tests, xunit setup/teardown hooks, conftest files,
pytest configuration, test packages, relative test imports, custom decorators,
plugins, dynamic test creation and unsupported pytest APIs. It also rejects
observable module metadata such as `__file__`, and namespace inspection/mutation.
Named collection metadata is accepted only within conservative initialization
rules; a helper call or compound initialization which could change it is rejected.
Use literal declarations or adapt the test explicitly.

Tests still obey Pystachy's [language compatibility](language/compatibility.md)
and [dynamic boundary contract](dynamic-any.md). There are no blanket `Any`
conversions, container copies to make boxing work, or CPython execution fallbacks.
An opted-in test can still expand numeric identity tracking through its imports;
concrete annotations alone do not prove absence of that cost.

## Failure and verification contract

Reports contain separate setup, call and teardown events plus a completion
record. Missing cases, missing call phases, duplicate events, interrupted runs,
malformed reports and disagreement with process status are execution errors.
Test stdout cannot impersonate the report protocol. Exit codes are 0 for success,
1 for test failures, 2 for collection/build/execution/oracle errors, and 5 for no
tests. A matching intentionally failing suite still returns 1.

```sh
make test-pytest-native
PYTHONPATH=ports PYSTACHY_PATH=ports python3 tools/pytest_native.py \
  examples/pytest_native --mode aot --compare --json build/pytest-native-aot.json
```

The target checks original pytest outcomes, negative controls, fixture lifecycle,
shared module state, native JIT/AOT, GC stress and a mixed `Any` fixture. It runs
inside the existing Lint job. The examples exercise current stdlib APIs and the
iniconfig/jdcal/json_repair ports. The 35 cases include 16 JSON-repair cases for
malformed/Unicode input, result objects, logs, fixture aliases and strict errors. These are
original tests, not claims of complete upstream suite support. Keep the existing
[943-case JSON-repair replay](../tests/upstream/json_repair/README.md) and extension
checks: this runner adds fixture/collection qualification rather than replacing
those broader API checks.

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
`--compare` checks the **adapted pytest suite** under
real CPython pytest. It does not validate the extraction against original unittest.
Retain the upstream pin, license, source and adaptation review, and run the original
selected unittest methods separately where available. The three fnmatch methods
above are a bounded qualification, not complete fnmatch coverage.

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
