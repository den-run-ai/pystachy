# json_repair parity corpus

Inputs derive from `mangiucugna/json_repair` **v0.64.8**, commit
`dc6d02b168656aa3dcaac6a119ecc47594d3526e`, under its [MIT license](LICENSE).
`manifest.json` records all 22 Python source hashes and the hashes of the seven
test modules and one shared case module used to extract inputs.

The **943 distinct input/API/option combinations** comprise 544 extracted
upstream schema-free calls and 399 task-focused cases, 192 of which cover
multilingual repair. This is an API replay corpus, **not execution of the complete
upstream test suite**; schema, file, CLI and internal-parser tests are outside its
scope.

The extractor resolves literal calls, simple string construction, local literal
assignments and loops, literal conditions and string interpolation, literal tables
whose items may interpolate strings, literal `pytest.mark.parametrize` decorators
(including tables they import from upstream's `tests/utils` case module), and the
upstream `_assert_object_repairs` helper. It parses but never executes or imports
test source to discover inputs. The manifest lists the unresolved calls: two
resource-dependent calls (Python's configurable integer conversion limit and a
runtime recursion depth search) and five that pass a schema.

Extracted calls retain their API, serialization defaults, parsing options,
`ensure_ascii=False` and repair logging. Unsupported keywords are reported rather
than silently dropped. Task cases exercise default, strict, streaming and
`skip_json_loads` modes. Returning logs takes priority over `return_objects=False`,
matching upstream. Inputs cover code strings, nested heterogeneous values,
Unicode, incomplete literals, comments, multiple records, duplicate keys and
long malformed strings with 10,000 commas or 5,000 braces before a far quote.

Pristine CPython 3.13.16 supplies the expected outcomes. Recursive tags retain
the distinction between booleans, integers, floats, strings, arrays, tuples,
objects and null. Objects retain key order. Strings use integer code points:
ordinary JSON escaping would make two surrogate characters and the equivalent
astral character indistinguishable. Inputs containing a literal adjacent surrogate
pair also carry `input_codepoints`, which the replay restores before calling the
API. The native runner emits round-trip float
representations, which the host checker converts to exact `float.hex()` values,
including negative zero. Error classes and exact messages are also compared.

**Case 67 exceeds signed 64-bit integer range.** It stays in the corpus and
passes through the native dynamic JSON decoder's token-promotion path. Additional
Unicode cases cover numeric suffixes, wide integers, combining marks, non-BMP
letters, whitespace, surrogates, nonletters and all supported parsing modes.
There is no silent exclusion or automatic known-failure allowance.

The corpus passes **943/943** under pristine 0.64.8 and the adapted port on
CPython 3.13.16, native JIT, native AOT, both native modes with program GC stress,
and the CPython companion extension under GC stress.
These results cover the recorded combinations; the separate Unicode audit checks
the five corrected character predicates across every Unicode code point.

CI replays the corpus natively in JIT and AOT (the `example-cli` verification step)
and through the CPython companion extension under GC stress (the `ffi` step). The
extension replay needs the pinned CPython as its oracle; under another interpreter
the FFI report lists it as skipped, which CI's FFI coverage check rejects.

The separate [native pytest qualifier](../../../tools/pytest_native_json_repair.py)
executes 53 real upstream pytest cases selected from five source modules. It
compares pristine upstream pytest, adapted pytest, generated CPython, native JIT
and native AOT, preserving exact case inventories and explicit exclusions.
Test functions/decorators and assertion bodies stay unchanged; public imports,
the existing dynamic JSON opt-in and one open-mapping helper annotation are
recorded in [pytest-selection.json](pytest-selection.json). Its 261-case inventory
covers only those five modules, not the complete upstream test tree. See
[qualification commands](../../../docs/pytest-native.md#qualify-original-upstream-tests).

## Replay

From the repository root, with CPython 3.13.16 on `PATH`:

```sh
python3.13 tools/json_repair_parity.py --write-inputs /tmp/json_repair_inputs.jsonl
PYTHONPATH=ports python3.13 tests/upstream/json_repair/replay.py /tmp/json_repair_inputs.jsonl > /tmp/json_repair_adapted.out
python3.13 tools/json_repair_parity.py /tmp/json_repair_adapted.out

PYSTACHY_PATH=ports ./pystachy build tests/upstream/json_repair/replay.py -o /tmp/json_repair_parity
/tmp/json_repair_parity /tmp/json_repair_inputs.jsonl > /tmp/json_repair_native.out
python3.13 tools/json_repair_parity.py /tmp/json_repair_native.out --report /tmp/json_repair_report.json
```

Generate replay inputs from `cases.json`; do not check in a second input copy
or raw output dumps. The checker requires every case exactly once and exits
nonzero on missing, duplicate or unexpected IDs, malformed output and every
content/type/error mismatch. It does not treat an early exit as a partial pass.

## Regenerate the oracle

Use a pristine upstream checkout and an isolated Python process:

```sh
git clone --depth 1 --branch v0.64.8 https://github.com/mangiucugna/json_repair.git /tmp/json_repair_upstream
python3.13 tools/build_json_repair_corpus.py --upstream /tmp/json_repair_upstream --output tests/upstream/json_repair
PYTHONPATH=/tmp/json_repair_upstream/src python3.13 tests/upstream/json_repair/replay.py /tmp/json_repair_inputs.jsonl > /tmp/json_repair_pristine.out
python3.13 tools/json_repair_parity.py /tmp/json_repair_pristine.out
```

The builder verifies the pinned commit and rejects tracked source modifications.
Upstream and adapted runs must be separate processes so Python's module cache
cannot select the wrong package. See the
[port guide](../../../ports/json_repair/PORT.md) for validation scope and native limitations.
