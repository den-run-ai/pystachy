# Native recursive JSON prototype

The prototype compiles a bounded `json.loads()`/`json.dumps()` implementation and
recursive JSON values through the existing JIT/AOT pipeline. It supports data
whose nesting and scalar alternatives are chosen by input text, without a
CPython interpreter or a user-visible node wrapper.

This establishes a generic representation for one useful closed set of types.
`Any` remains inference-only in its supported positions. There is no runtime
profiling, online compilation or automatic skew-based specialization.

## Values and ownership

The library declares:

```python
type JSONValue = None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
```

The compiler accepts this nongeneric PEP 695 shape and smaller closed unions
whose members are the same scalar types, `None`, `list[Self]` and
`dict[str, Self]`. There must be at least two distinct non-`None` alternatives;
a recursive list alone, even with `None`, is not supported. Recursion must occur
directly through these containers. Mutual recursion, generic recursive aliases,
recursive tuples, other dict-key types and arbitrary recursive object types
remain unsupported. Imports and ordinary aliases of an accepted alias retain
its graph. See [type aliases](language/typing.md#recursive-value-aliases-prototype).

The compiler keeps a finite named edge for recursive container slots, rather
than expanding an annotation to a fixed depth. Values use existing immutable
16-byte union tag/payload boxes, with `None` represented by null. Container
payloads keep the original list/dict pointer; their recursive element/value
slots contain these boxed values. The existing conservative collector scans
those references. Descriptor strings use finite backward references for recursive
edges; runtime traversal follows the descriptor alongside each value.

`isinstance()` narrows local values and parameters before indexing, iteration,
arithmetic or mutation. Narrowing preserves identity: two references to the same
parsed list see each other's changes. Existing typed containers remain invariant;
an existing `list[int]` is not reinterpreted or implicitly copied into
`list[JSONValue]`. Construct recursive storage explicitly or obtain it from
`loads()`. Existing restrictions on narrowing mutable globals remain in force.

Recursive values support the existing truth, representation and builtin-value
equality paths, including numeric cross-type comparison. Comparisons retain
separate descriptors for both operands. Shared container identity is recognized;
distinct cyclic structures eventually raise `RecursionError`. `repr()` uses
cycle markers. Runtime representation/comparison have internal recursion budgets
(currently 512), counted independently of the JSON codec's 256-container budget.
Ordering requires narrowing. These are bounded builtin-value operations, not
general user-defined dynamic dispatch.

The shared comparison and representation helpers conservatively gain raising
effects in typed IR because their depth guards can fail. This also affects
nonrecursive callers; the existing key-effect model can expand those effects
further for keys with a custom representation. Three object-key effect snapshots
record that intentional overapproximation. Narrowing effects by descriptor is
follow-up work, and existing-workload performance needs separate review.

The inherited unboxed-float identity rule also applies: separately decoded
`[NaN]` lists compare unequal here, while CPython's cached decoder NaN can make
them compare equal. See [numeric deviations](language/compatibility.md#numbers).

## JSON API

| API | Supported behavior |
|---|---|
| `loads(s: str)` | Scalars, mixed arrays, nested objects; string keys; whitespace; last duplicate key wins |
| `dumps(obj: JSONValue)` | Scalars and recursive lists/dicts; insertion-order objects; shared aliases; cycle detection |
| Encoder keywords | `ensure_ascii=True`, `allow_nan=True`, `sort_keys=False`, `separators=None` or a two-string tuple |
| `JSONDecodeError` | `ValueError` subclass with `msg`, `doc`, `pos`, `lineno`, `colno` and formatted error text |

Strings support JSON escapes, Unicode code points, surrogate-pair decoding and
lone surrogates, as CPython's JSON codec does. Error positions count characters.
`ensure_ascii=True` escapes non-ASCII text; `False` retains it in the returned
string. Writing lone surrogates remains subject to the runtime's separate
[text encoding rules](language/compatibility.md#text-and-file-positions).

As with CPython's defaults, the decoder accepts `NaN`, `Infinity` and
`-Infinity`; the encoder emits them unless `allow_nan=False`, which raises
`ValueError`. The parser rejects malformed text and trailing data with
`JSONDecodeError`. It does not preserve numeric spellings or duplicate keys.

Deliberate limits:

- Integer tokens must fit signed 64-bit storage; a larger integer raises
  `OverflowError`. Floating-point tokens use native double precision.
- Decoding and encoding permit at most 256 nested containers and raise
  `RecursionError` beyond that budget. Circular serialization raises
  `ValueError: Circular reference detected`.
- Input is `str`; bytes/bytearray input, `load()`/`dump()`, `JSONDecoder`,
  `JSONEncoder`, hooks, custom conversion functions, `default`, `skipkeys`,
  `check_circular`, `strict` and indentation are not implemented.
- Object keys must be strings; tuple serialization and arbitrary user objects
  are outside the `JSONValue` representation. Unsupported APIs/types are normally
  compilation errors, not CPython's runtime errors.

## Consumer example

```python
import json


def update(text: str) -> str:
    value = json.loads(text)
    if isinstance(value, dict):
        rows = value.get("rows")
        if isinstance(rows, list):
            rows.append(None)
        value["checked"] = True
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


print(update('{"rows":[{"amount":7},{"amount":2.5},"unknown"]}'))
```

The [record-processing benchmark](json-benchmark.md) uses nested API/event
records with common integer amounts and rare floats, nulls, missing fields and
other values. It separates parsing, processing and their combination, and compares
ordinary execution with a hand-written guarded control. Correct generic fallback
behavior is required for every alternative. This prototype makes no performance
claim and does not demonstrate a benefit from online specialization. A
[measured checkpoint](reports/native-json-2026-10-18.md) finds parsing dominates
this workload and the guarded-processing results remain inconclusive.

## Validation and reproduction

Use the pinned CPython from `.python-version` and the documented LLVM toolchain.
From the repository root:

```sh
PYTHON=python3.13 tests/record.sh json_roundtrip json_unicode json_errors json_mutation
PYSTACHY_GC_STRESS_PROGRAM=1 make test-py PY=python3.13 FILES="tests/json_*.py tests/recursive_alias_*.py tests/deviations/json_limits.py tests/deviations/recursive_alias_limits.py"
python3.13 tools/json_check.py --native --gc-stress
python3.13 tools/bench_json.py --compiler "python3.13 -m pystachy" --smoke
```

The regular fixtures compare against CPython's standard `json`; the separate
[JSON limit fixture](../tests/deviations/json_limits.py) records deliberate integer
and codec depth differences. The [runtime limit fixture](../tests/deviations/recursive_alias_limits.py)
checks deep values, cycles and reuse after exception unwinding.
[`tools/json_check.py`](../tools/json_check.py) generates
deterministic nested values and malformed text, compares encoder options and
exact decoder diagnostics, then runs the same input corpus through native JIT/AOT.
`--seed`, `--cases` and `--invalid` reproduce or resize its corpus. Compiler and
runtime changes still require the full verification matrix before merge; these
focused checks do not replace bootstrap, IR/effect contracts or broader GC tests.
