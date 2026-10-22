# json_repair parity corpus

Inputs derive from `mangiucugna/json_repair` **v0.64.1**, commit
`ace9b23cb7fc6757775d5fafbfaaa9a88363a573`, under its [MIT license](LICENSE).
`manifest.json` records all 22 Python source hashes and the seven test-file
hashes used to extract inputs.

The **557 distinct input/API/option combinations** comprise 350 extracted
upstream schema-free calls and 207 task-focused cases. This is an API replay
corpus, **not execution of the complete upstream test suite**. The extractor
resolves literal calls, simple string construction, local literal assignments
and literal `pytest.mark.parametrize` decorators. Twelve unresolved or large
stress call variants remain listed in the manifest. Schema, file, CLI and
internal-parser tests are outside its scope.

The original 466 cases compare repaired objects in default, strict, streaming
and `skip_json_loads` modes. The remaining 91 exercise serialized string
returns, `ensure_ascii=False`, repair logs and the `loads` wrapper. Returning
logs takes priority over `return_objects=False`, matching upstream. Inputs
cover code strings, nested heterogeneous values, Unicode, incomplete literals,
comments, multiple records and duplicate keys.

Pristine CPython 3.13.16 supplies the expected outcomes. Recursive tags retain
the distinction between booleans, integers, floats, strings, arrays, tuples,
objects and null. Objects retain key order. Strings use integer code points:
ordinary JSON escaping would make two surrogate characters and the equivalent
astral character indistinguishable. The native runner emits round-trip float
representations, which the host checker converts to exact `float.hex()` values,
including negative zero. Error classes and exact messages are also compared.

**Case 57 exceeds Pystachy's signed 64-bit integer range.** It stays in the
corpus and the checker fails on it. Report the actual matched count and this
limitation; there is no silent exclusion or automatic known-failure allowance.

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
**557/557**; see the port guide for native evidence and limitations.
