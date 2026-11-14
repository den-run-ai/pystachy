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

Node IDs (`path::test` or `path::test[id]`) select cases as pytest's arguments do:
in the order given, a repeated ID once, and an unknown ID is an error. Give node IDs
for every argument, with one module's IDs together. The module is still imported
whole. The real pytest oracle runs the same selection.

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
checkout. `--python` selects the oracle interpreter; a missing pytest is reported
as such. `--timeout` bounds each build/run/oracle subprocess.

Each failure shows the native exception's class and message (`KeyError: 'missing'`),
as pytest's summary does. A comparison assertion with no message (`==`, `!=`, `<`,
`<=`, `>`, `>=`, `in`, `not in`) also shows its operands' `repr()`s, such as
`assert 4 == 5`. Names are read again for this; other operands are kept in reserved
temporaries as they are evaluated, once and in order. When the original pytest also
fails, its own report follows. A case or phase whose outcome differs from pytest's
is listed as `MISMATCH`, and a summary line counts the outcomes. If the native
compiler rejects the operand code (for example, `repr()` of a function), the program
was never started, and the suite is built again with plain assertion messages; the
JSON keeps that build's error, and later runs of the unchanged code skip it.
Compile errors name the generated module, whose lines can differ from the source.

`--root` defaults to the current directory. Selected files must be inside it and
must share one source directory. The latter restriction preserves sibling-import
resolution; combining arbitrary directories requires additional import support.
All selected modules are collected before execution, imported before tests run,
and executed in one process, preserving shared imported-module state. Empty test
modules are imported too: an import failure cannot disappear from the result.
Generated modules keep their test modules' names, as pytest imports them, so
`__module__` and `repr()` of their classes and functions match. A module that
cannot be collected is reported without running the pytest oracle.

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
- Inline `pytest.param(..., id="case", marks=...)` entries with static
  skip/skipif/xfail marks. Named tables containing `pytest.param` and computed
  parameter metadata remain unsupported.
- Function-scoped return/yield fixtures defined in the selected module,
  dependencies and literal `autouse`.
  `@pytest.fixture(name="alias")` exposes an explicit public fixture name.
  Repeated requests share one fixture value within a test. Teardown resumes yield
  fixtures in reverse setup order, including after a test fails or later fixture
  setup fails; one cleanup failure does not discard the remaining cleanup.
- `pytest.raises(ExceptionClass, match="regex")` as a context manager, including
  guarded `.value` and `.type`; exception tuples, `check=`, callable form and
  compiled regexes are outside this subset.
- `pytest.fail`, `pytest.skip`, `pytest.xfail`, and static skip/skipif/xfail marks,
  including strict XPASS and `run=False`. Boolean conditional markers require
  an explicit reason, as in pinned pytest.
- A test decorator's `skipif` condition may be an expression, such as
  `sys.platform == "win32"`: it is evaluated once at import, in decorator order, as
  pytest's decorator is. String conditions, which pytest evaluates as code, and
  conditions inside `pytest.param` remain literal-only.
- `@pytest.mark.usefixtures("name", ...)` with literal names, set up after autouse
  fixtures and before argument fixtures, nearest decorator first, as pytest does.
- Marks that only label tests, such as `@pytest.mark.slow`, with literal arguments.
  The isolated oracle loads no plugin that gives them meaning; `-m` selection is
  not supported. `filterwarnings` and other marks with behavior are rejected.
- `if __name__ == "__main__":` blocks without `else`, which never run in a module
  that pytest imports, are left out.
- Explicit per-source dynamic `Any` opt-in for supported open payloads. The runner
  itself stores metadata, statuses and exceptions in concrete types.

Unsupported source forms detected by the collector are errors, never implicit skips.
Imported fixtures are unsupported; the default oracle checks their observable
collection and phase effects. The collector rejects
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
inside the existing x86-64 `hosted` CI job on code PRs, main pushes and manual runs.
The examples exercise current stdlib APIs and the
iniconfig/jdcal/json_repair ports. The 35 cases include 16 JSON-repair cases for
malformed/Unicode input, result objects, logs, fixture aliases and strict errors. These are
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
