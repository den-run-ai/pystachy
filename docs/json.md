# Native JSON

Pystachy provides an experimental, bounded `json.loads()`/`json.dumps()` implementation
and recursive JSON values through the JIT/AOT pipeline. It supports data
whose nesting and scalar alternatives are chosen by input text, without a
CPython interpreter or a user-visible node wrapper.

This establishes a generic representation for one useful closed set of types.
`Any` remains inference-only in its supported positions, except in modules that opt in to
[dynamic `Any`](dynamic-any.md). There is no runtime profiling, online compilation or automatic
skew-based specialization.

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

Save this as `jsondemo.py`, then run it or build an executable:

```sh
./pystachy run jsondemo.py
./pystachy build jsondemo.py -o jsondemo
./jsondemo
```

Both modes print:

```text
{"checked":true,"rows":[{"amount":7},{"amount":2.5},"unknown",null]}
```

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
cycle markers. Runtime representation and comparison follow at most 512
recursive alias edges before raising `RecursionError`; the edges are counted
independently of the JSON codec's 256-container budget, and other reprs (a
class's own `__repr__`, say) remain limited only by the native stack. Ordering
requires narrowing, and so does `==` on a union that holds a
recursive alias beside members holding objects or sets. These are bounded
builtin-value operations, not general user-defined dynamic dispatch.

Recursive aliases are nominal: two aliases with the same members are different
types, so a program's own JSON alias does not exchange values with
`json.JSONValue`. A runtime signature that builds a tuple around a recursive
value (`list(d.items())` for `d: dict[str, JSONValue]`) can also spell its type
differently from an annotation; both are rejected at compile time, not
miscompiled.

Only a recursive alias's edge lets a value nest without bound, so only a
descriptor that holds one can reach those depth guards. The runtime operations
that compare or print by descriptor declare this as the conditional effect `R?`
([typed IR](typed-ir.md#effects)): they may raise where their descriptor holds
such an edge, and programs without recursive values compile as they did before
recursive aliases.

The inherited unboxed-float identity rule also applies: separately decoded
`[NaN]` lists compare unequal here, while CPython's cached decoder NaN can make
them compare equal. See [numeric deviations](language/compatibility.md#numbers).

## JSON API

| API | Supported behavior |
|---|---|
| `loads(s: str)` | Scalars, mixed arrays, nested objects; string keys; whitespace; last duplicate key wins |
| `dumps(obj: JSONValue)` | Scalars and recursive lists/dicts; insertion-order objects; shared aliases; cycle detection |
| Encoder keywords | `ensure_ascii=True`, `allow_nan=True`, `sort_keys=False`, `separators=None` or a two-string tuple |
| `JSONDecoder()` | Default `decode(s)` and `raw_decode(s, idx=0)`; the latter returns a value and character end offset, without skipping leading whitespace or rejecting trailing text |
| `JSONDecodeError` | `ValueError` subclass with `msg`, `doc`, `pos`, `lineno`, `colno` and formatted error text |

Strings support JSON escapes, Unicode code points, surrogate-pair decoding and
lone surrogates, as CPython's JSON codec does. Error positions count characters.
`JSONDecoder.decode()` calls a subclass's `raw_decode()` override after skipping leading
JSON whitespace and preserves its effects, result and exceptions. Dispatch through
a base-annotated decoder follows the compiler's common override-return contract;
use the quoted annotation `"tuple[json.JSONValue, int]"` for that path. Concrete
subclass calls can retain a narrower return annotation.
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
- Input is `str`; bytes/bytearray input, `load()`/`dump()`, configured `JSONDecoder` constructors,
  `JSONEncoder`, hooks, custom conversion functions, `default`, `skipkeys`,
  `check_circular`, `strict` and indentation are not implemented.
- Object keys must be strings; tuple serialization and arbitrary user objects
  are outside the `JSONValue` representation. Unsupported APIs/types are normally
  compilation errors, not CPython's runtime errors.

## In modules that opt in to dynamic `Any`

The public `JSONDecoder` keeps recursive `JSONValue` storage and its ordinary class
identity. A native-only `_raw_decode(s, idx=0)` adapter decodes into `Any` containers
when called directly from an opt-in module. Ports can retain CPython execution with
this fallback:

```python
# pystachy: dynamic-any
import json
from typing import Any

try:
    from json import _raw_decode as raw_decode
except ImportError:
    def raw_decode(s: str, idx: int = 0) -> tuple[Any, int]:
        return json.JSONDecoder().raw_decode(s, idx)
```

This extension is for direct calls, like the `json.loads()` dynamic-storage route;
passing the adapter as a callable value does not request dynamic result storage.

In a module that opts in to [dynamic `Any`](dynamic-any.md), `json.loads()` decodes into `Any`'s
containers wherever its result becomes `Any` storage: an `Any` variable, argument or return value,
or a `list[Any]`, `dict[str, Any]` or `list[dict[str, Any]]`, which have `Any`'s layout there.
`json.dumps()` encodes a value that holds `Any` values, and a display or comprehension passed to
it, by walking `Any` values. Both are lib's `_pystachy_json_any.py`, which the compiler calls for
`json`'s functions in such a module (#779). The document is then one set of objects that typed
code (`dict[str, Any]`, `list[dict[str, Any]]`) and `Any` code share, with no copy: a change made
through either shows through the other (`tests/programs/inference/dynany_json.py`,
`tests/programs/inference/dynany_json_app.py`).

`dumps()` of `Any` values writes tuples as arrays, and int, float, bool and `None` keys as
strings, and takes CPython's `skipkeys`, `check_circular` and `default` too. It raises CPython's
`TypeError`s: `Object of type C is not JSON serializable` for a value JSON cannot hold, and `keys
must be str, int, float, bool or None, not C`. A `default` callback's result becomes an `Any` value,
so the callback is declared `-> Any`: one declared `-> dict[str, int]` is rejected, as a typed
container is wherever it would become an `Any` value. Its other limits are those listed above.
Without `sort_keys`, callbacks that delete and reinsert keys or clear and repopulate the dict
can change output order or entries compared with CPython's live dict-table traversal (the
[dynamic `Any` deviation](dynamic-any.md#selecting-dynamic-storage)).
Elsewhere, including where the result has a typed or no annotation (`doc = json.loads(s)`),
`json`'s own functions and `JSONValue` storage stay as they are.

## Decoder

`loads()` scans the UTF-8 bytes of its argument with integer comparisons, so it
creates no one-character strings and translates no code-point offsets while
scanning. Pystachy's `str.encode()` returns the string's own UTF-8 storage unless
the text contains a character from U+D000 to U+DFFF; then it checks and copies
every character. Every delimiter, digit and escape is ASCII: the scanner stops
only at character boundaries, and an error converts its byte offset into the
character position CPython reports. A string without escapes is one slice of the
bytes, decoded without an error handler or codec lookup; a document that holds
lone surrogates, which `encode()` rejects, decodes its slices with
`surrogatepass`. Pystachy reads files
([deviation](language/compatibility.md#text-and-file-positions)), `input()` and
`sys.argv` without checking their bytes, and `encode()` returns such text
unchanged. When a slice is not UTF-8, `loads()` parses the text again and takes
each string from the `str` itself, at character offsets counted as `str` counts
them, as the character-by-character decoder this one replaced did. Integers of up
to 18 digits accumulate as they are scanned; longer ones keep the signed 64-bit
bound check.

A 64-entry cache indexed by key length and first byte, and checked byte for
byte, returns the string of an equal object key seen earlier in the same
document. Records of one shape then share their key objects, as CPython's
decoder memo makes them do, and dictionary insertion reuses those keys' cached
hashes. The cache lives for one `loads()` call.

## Encoder

`dumps()` appends each piece of its output to one list and joins it once. A
string's UTF-8 bytes are scanned once: a string with no control character, quote
or backslash, and with `ensure_ascii=True` no byte from 127 on, goes between its
quotes whole. Otherwise, with `ensure_ascii=True`, it is escaped from those
bytes: each run of printable ASCII is copied as one slice, and each `\uXXXX`
appended as three pieces that need no new string. Text that `encode()` rejects
(lone surrogates), and text that needs escapes with `ensure_ascii=False`, is
escaped character by character, again copying the runs between escapes whole. A
byte that starts no UTF-8 sequence is escaped as the character `str` counts it
as.

In the [recorded encoder benchmark](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/native-json-encoder-2026-10-19.md),
AOT and JIT `dumps()` of 5,000-record documents took 1.1–1.6 times CPython's C
encoder time. Escaping non-ASCII text with `ensure_ascii=True` was the slowest
case. The report includes inputs, measurements and comparisons with the earlier encoder.

## Benchmarks

The [record-processing benchmark](json-benchmark.md) uses nested API/event
records with common integer amounts and rare floats, nulls, missing fields and
other values. It separates parsing, processing and their combination, and compares
ordinary execution with a hand-written guarded control. Correct generic fallback
behavior is required for every alternative. The
[parser measurements](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/native-json-parser-2026-10-18.md) compare CPython,
PyPy and Pystachy, with parsing and processing timed separately. They do not
establish a reliable benefit from the hand-written guarded path in JIT or AOT.
The [initial checkpoint](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/native-json-2026-10-18.md) retains the earlier
parser baseline and experiment details.

## Validation and reproduction

Use the pinned CPython from `.python-version` and the documented LLVM toolchain.
From the repository root:

```sh
PYSTACHY_GC_STRESS_PROGRAM=1 make test-py PY=python3.13 FILES="tests/programs/library/json_*.py tests/programs/inference/recursive_alias_*.py tests/deviations/json_*.py tests/deviations/recursive_alias_limits.py"
python3.13 tools/json_check.py --native --gc-stress
python3.13 tools/bench_json.py --compiler "python3.13 -m pystachy" --smoke
```

The regular fixtures compare against CPython's standard `json`; the separate
[JSON limit fixture](../tests/deviations/json_limits.py) records deliberate integer
and codec depth differences. The [runtime limit fixture](../tests/deviations/recursive_alias_limits.py)
checks deep values, cycles and reuse after exception unwinding.
[`tests/programs/library/json_scanner.py`](../tests/programs/library/json_scanner.py) covers the byte scanner's
boundaries: positions after multibyte text, documents holding lone surrogates,
repeated and colliding object keys, and integers around 18 digits.
[`tools/json_check.py`](../tools/json_check.py) generates
deterministic nested values and malformed text, compares encoder options and
exact decoder diagnostics, then runs the same input corpus through native JIT/AOT.
A second generator adds raw non-ASCII and lone-surrogate documents, malformed
Unicode text and colliding object keys. Native runs receive each source as
decimal code points, since a JSON-escaped pair of lone surrogates would arrive
as the one character it encodes. `--seed`, `--cases`, `--invalid` and
`--unicode-invalid` reproduce or resize its corpus. Compiler and
runtime changes still require the full verification matrix before merge; these
focused checks do not replace bootstrap, IR/effect contracts or broader GC tests.
