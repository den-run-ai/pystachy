# json_repair parity corpus

Inputs derive from `mangiucugna/json_repair` **v0.64.1**, commit
`ace9b23cb7fc6757775d5fafbfaaa9a88363a573`, under its [MIT license](LICENSE).
`manifest.json` records all 22 Python source hashes and the seven test-file
hashes used to extract inputs.

The **645 distinct input/API/option combinations** comprise 438 extracted
upstream schema-free calls and 207 task-focused cases. This is an API replay
corpus, **not execution of the complete upstream test suite**. The extractor
resolves literal calls, simple string construction, local literal assignments
and loops, literal conditions and string interpolation, literal `pytest.mark.parametrize` decorators, and the upstream
`_assert_object_repairs` helper. It never executes test source to discover inputs.
The two resource-dependent calls that remain unresolved are listed in the
manifest: Python's configurable integer conversion limit and a runtime recursion
depth search. Schema, file, CLI and internal-parser tests are outside its scope.

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
astral character indistinguishable. The native runner emits round-trip float
representations, which the host checker converts to exact `float.hex()` values,
including negative zero. Error classes and exact messages are also compared.

**Case 59 exceeds signed 64-bit integer range.** It stays in the corpus and now
passes through the port's promoting number parser. Native JIT, AOT and both
modes with collection at every allocation match **645/645**. There is no silent
exclusion or automatic known-failure allowance.

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
git clone --depth 1 --branch v0.64.1 https://github.com/mangiucugna/json_repair.git /tmp/json_repair_upstream
python3.13 tools/build_json_repair_corpus.py --upstream /tmp/json_repair_upstream --output tests/upstream/json_repair
PYTHONPATH=/tmp/json_repair_upstream/src python3.13 tests/upstream/json_repair/replay.py /tmp/json_repair_inputs.jsonl > /tmp/json_repair_pristine.out
python3.13 tools/json_repair_parity.py /tmp/json_repair_pristine.out
```

The builder verifies the pinned commit and rejects tracked source modifications.
Upstream and adapted runs must be separate processes so Python's module cache
cannot select the wrong package. Pristine CPython replay was checked at
**645/645**; see the port guide for native evidence and limitations.
