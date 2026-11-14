# json_repair parity corpus

Inputs derive from `mangiucugna/json_repair` **v0.64.9**, commit
`36d7a6ed53e777b5a5b9017e33d35ea2af8b7c6e`, under its [MIT license](LICENSE).
`manifest.json` records all 22 Python source hashes and the hashes of the seven
test modules and one shared case module used to extract inputs.

The **962 distinct input/API/option combinations** comprise 563 extracted
upstream schema-free calls and 399 task-focused cases, 192 of which cover
multilingual repair. The 943 combinations of the 0.64.8 corpus are all retained,
with unchanged outcomes. This is an API replay
corpus, **not execution of the complete upstream test suite**. The extractor
resolves literal calls, simple string construction, local literal assignments
and loops, literal conditions and string interpolation, literal tables whose items
may interpolate strings, literal `pytest.mark.parametrize` decorators (including
tables they import from upstream's `tests/utils` case module), and the upstream
`_assert_object_repairs` helper. It parses but never executes or imports test source
to discover inputs. The manifest lists the unresolved calls: three whose input no
literal gives (Python's configurable integer conversion limit, a runtime recursion
depth search and a parametrized buffered-input comparison) and five that pass a schema. Schema, file, CLI and internal-parser
tests are outside its scope; [schema-guided repair](#schema-guided-repair) has its own evidence.

Extracted calls retain their API, serialization defaults, parsing options,
`ensure_ascii=False` and repair logging. Unsupported keywords are reported rather
than silently dropped. Task cases exercise default, strict, streaming and
`skip_json_loads` modes. Returning logs takes priority over `return_objects=False`,
matching upstream. Inputs cover code strings, nested heterogeneous values,
Unicode, incomplete literals, comments, multiple records, duplicate keys and
long malformed strings with 10,000 commas or 5,000 braces before a far quote.

Pristine upstream under CPython supplies the expected outcomes; the manifest records the
interpreter (3.13.18 for this corpus, a patch release of the pinned 3.13.16). Recursive tags retain
the distinction between booleans, integers, floats, strings, arrays, tuples,
objects and null. Objects retain key order. Strings use integer code points:
ordinary JSON escaping would make two surrogate characters and the equivalent
astral character indistinguishable. Inputs containing a literal adjacent surrogate
pair also carry `input_codepoints`, which the replay restores before calling the
API. The native runner emits round-trip float
representations, which the host checker converts to exact `float.hex()` values,
including negative zero. Error classes and exact messages are also compared.

**Case 76 exceeds signed 64-bit integer range.** It stays in the corpus and
passes through the native dynamic JSON decoder's token-promotion path. Additional
Unicode cases cover numeric suffixes, wide integers, combining marks, non-BMP
letters, whitespace, surrogates, nonletters and all supported parsing modes.
There is no silent exclusion or automatic known-failure allowance.

The corpus passes **962/962** under pristine 0.64.9 and the port on CPython,
native JIT and native AOT, and both native modes with program GC stress. The CPython
companion extension replays it under GC stress in the FFI suite.
These results cover the recorded combinations; the separate Unicode audit checks
the five corrected character predicates across every Unicode code point.

CI replays the corpus natively in JIT and AOT (the `example-cli` verification step)
and through the CPython companion extension under GC stress (the `ffi` step). The
extension replay needs the pinned CPython as its oracle; under another interpreter
the FFI report lists it as skipped, which CI's FFI coverage check rejects.

The separate [native pytest qualifier](../../../tools/pytest_native_json_repair.py)
executes real upstream pytest cases selected from five source modules: 53 when it last ran,
against 0.64.8. Its selection is pinned to 0.64.9 with this corpus and has not been run
again: it needs the pinned CPython 3.13.16. It
compares pristine upstream pytest, adapted pytest, generated CPython, native JIT
and native AOT, preserving exact case inventories and explicit exclusions.
Test functions/decorators and assertion bodies stay unchanged; public imports,
the existing dynamic JSON opt-in and one open-mapping helper annotation are
recorded in [pytest-selection.json](pytest-selection.json). Its inventory (261 cases at
0.64.8) covers only those five modules, not the complete upstream test tree.

Upstream's whole suite also runs against the port under CPython, with the port in place of
`src/json_repair`: of the 413 tests that pass for pristine 0.64.9 without `jsonschema`
installed, 376 pass for the port. The other 37 read what the port replaces: 35 the schema
module's internals and 2 the string scanner's accumulator state. See
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

## Differential fuzz

[json_repair_fuzz.py](../../../tools/json_repair_fuzz.py) generates inputs beyond this corpus
and replays them, with this directory's replay program and the checker's type-exact comparison,
through pristine upstream under CPython (the oracle, whose sources it checks against the
manifest's hashes), the port under CPython and the port's native build:

```sh
python3.13 tools/json_repair_fuzz.py --upstream /tmp/json_repair_upstream --seed 1 --cases 250000 --jit --gc-stress 500
```

Each generated text runs under three of eleven API and option combinations. There are four
schema-free families of text. `mixed` mutates this corpus's inputs and renderings of random values. `long`
puts quotes, escapes and structural characters at the 64-code-point chunk boundaries of the
port's string scanner. `number` builds numeric tokens. `comment` puts terminators at the
boundaries of the comment scanner's windows.

| Family | Cases | Distinct texts | Upstream raises | Port under CPython | Native AOT | Native JIT | AOT, stressed collector (first 500) |
|---|---|---|---|---|---|---|---|
| `mixed` | 250,000 | 68,876 | 12,735 | equal | equal | equal | equal |
| `long` | 250,000 | 83,289 | 9,124 | equal | equal | equal | equal |
| `number` | 250,000 | 78,036 | 3,468 | equal | equal | equal | equal |
| `comment` | 250,000 | 83,326 | 17,233 | equal | equal | equal | equal |

The run above, with seed 1 on 2026-11-12, the compiler of commit `2321d2ad` and CPython 3.13.18
(a patch release of the pinned 3.13.16), found no difference: all 1,000,000 cases match upstream
in each configuration, and so do the first 500 of each family with the native collector stressed
(a stressed replay takes seconds for a case with long output). This is evidence for these
generated inputs, not proof of parity. The texts hold no surrogate code points, and the generator
gives the same texts under CPython 3.11 to 3.13. CI does not run the fuzz: it needs an upstream
checkout. [Its unit tests](../../../tools/test_json_repair_fuzz.py) run in `make check-fast`.

## Schema-guided repair

The corpus above is schema-free. Schema-guided repair has its own evidence, because its
oracle needs `jsonschema`, which upstream validates with and the port
[replaces](../../../ports/json_repair/PORT.md#schema-guided-repair):

- The fuzz's `schema` family repairs values that nearly fit a generated JSON Schema, in both
  repair modes, after 118 runs of 48 documented examples. Its oracle pins the two orders that
  upstream leaves to the hash seed (an object's additional properties, a schema's required
  names) to the port's. It needs `jsonschema` in the CPython that runs it:

  ```sh
  python3.13 tools/json_repair_fuzz.py --upstream /tmp/json_repair_upstream --family schema --seed 1 --cases 30000 --jit --gc-stress 500
  ```

  | Seed | Cases | Distinct texts | Upstream raises | Port under CPython | Native AOT | Native JIT | AOT, stressed collector (first 500) |
  |---|---|---|---|---|---|---|---|
  | 1 | 30,000 | 7,464 | 20,235 | equal | equal | equal | equal |

  This run, on 2026-11-12 with jsonschema 4.26.0 and CPython 3.13.18, found no difference.
  Upstream raises in two thirds of the cases: a repair that cannot satisfy its schema is an
  error, and so are the option combinations it rejects.
- [json_repair_validator_fuzz.py](../../../tools/json_repair_validator_fuzz.py) compares the
  port's validator alone with `jsonschema`, on generated schemas of drafts 4 to 2020-12, valid
  and invalid, and instances for them: `check_schema()`, `validate()` and `is_valid()`, by
  error class and message. Seeds 1 and 2 with 25,000 schemas each (31,820 of them valid, with
  190,920 instances) gave no difference. A reference that the port leaves out is counted
  (1,899 times there), not compared.
- CI runs neither. It runs what they recorded:
  [the native regression](../../../tests/programs/apps/port_json_repair_schema.py) replays 182
  of the family's cases against upstream's outcomes (its `.in` file, written by `--record`),
  and [the validator's unit tests](../../../tools/test_json_repair_validator.py) hold it to
  `jsonschema`'s answers for [123 hand-written cases](validator_answers.json) (`--answers`).
  The 26 static-anchor cases also run as a dedicated native regression, including
  schema-versus-instance positions, recursive anchors, error messages and mixed drafts.
  Its additional cross-draft `evolve()` checks retain the root resource's dialect.
- [metaschemas.py](metaschemas.py) regenerates the port's metaschemas from
  jsonschema-specifications 2025.9.1, whose files' hashes it pins.

## Regenerate the oracle

Use a pristine upstream checkout and an isolated Python process:

```sh
git clone --depth 1 --branch v0.64.9 https://github.com/mangiucugna/json_repair.git /tmp/json_repair_upstream
python3.13 tools/build_json_repair_corpus.py --upstream /tmp/json_repair_upstream --output tests/upstream/json_repair
PYTHONPATH=/tmp/json_repair_upstream/src python3.13 tests/upstream/json_repair/replay.py /tmp/json_repair_inputs.jsonl > /tmp/json_repair_pristine.out
python3.13 tools/json_repair_parity.py /tmp/json_repair_pristine.out
```

The builder verifies the pinned commit and rejects tracked source modifications.
Upstream and adapted runs must be separate processes so Python's module cache
cannot select the wrong package. See the port guide for validation scope and
native limitations.
