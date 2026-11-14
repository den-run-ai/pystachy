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
independently of the JSON codec's bound on nesting, and other reprs (a
class's own `__repr__`, say) remain limited by the recursion limit and the native stack's floor. Ordering
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
| `load(fp)`, `dump(obj, fp)` | `loads(fp.read())` and `fp.write(dumps(obj))` of a text file; `dump()` takes the encoder keywords and writes the document in one piece |
| Encoder keywords | `ensure_ascii=True`, `allow_nan=True`, `sort_keys=False`, `separators=None` or a two-string tuple, `indent=None`, an `int` or a `str` |
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

- Typed `JSONValue` integer tokens must fit signed 64-bit storage; a larger integer
  raises `OverflowError`. Dynamic `Any` decoding promotes larger integers as described
  below. Floating-point tokens use native double precision.
- Decoding nests as CPython's C decoder does on Linux: 9,998 containers at any recursion
  limit, and beyond them `RecursionError: maximum recursion depth exceeded while decoding a
  JSON array from a unicode string` (or `object`). The first 64 containers are two counted
  calls each; deeper ones are decoded without calls, so neither `sys.setrecursionlimit()` nor
  the native stack bounds them.
- `dumps()` nests as CPython's C encoder does on Linux, with or without an `indent`: 9,998
  containers at any recursion limit, and beyond them `RecursionError: maximum recursion depth
  exceeded while encoding a JSON object`. The first 64 containers are a counted call each (two
  for a dict of `Any` values); deeper ones are encoded without calls. For `Any` values, a
  `default()` conversion in progress counts as a container does, and a call of `default()`
  needs one more level, where it raises `RecursionError: maximum recursion depth exceeded`:
  9,997 conversions and containers around a call.
- `dump()` is native recursion, a counted call for each container, which
  `sys.setrecursionlimit()` bounds as it bounds CPython's `dump()`, whose encoder is Python
  code (#1021): about 1,000 containers at the default limit. Under a raised limit, a fixed
  bound of 2,000 containers keeps it within an 8 MiB native stack in every measured
  configuration, where CPython's goes on
  ([deviation](../tests/deviations/json_limits.py)). Circular serialization raises
  `ValueError: Circular reference detected`.
- Input is `str`; bytes/bytearray input, configured `JSONDecoder` constructors,
  `JSONEncoder`, hooks, custom conversion functions, `default`, `skipkeys`,
  `check_circular` and `strict` are not implemented.
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

Code written for CPython needs no adapter: `json.JSONDecoder().raw_decode(s, idx)`, called on
a default decoder made in the same expression, decodes into `Any` containers where its result
is expected to hold `Any` values, as `json.loads()` does. A return annotation gives that
expectation, or the declared types of the names it is unpacked into:

```python
value: Any
end: int
value, end = json.JSONDecoder().raw_decode(text)
```

A decoder kept in a variable, and a result whose type nothing declares, stay typed
(`tests/programs/inference/dynany_json_decoder_any.py`). `json.load()` and `json.dump()`
follow `loads()` and `dumps()` (`tests/programs/inference/dynany_json_load_dump.py`).

In a module that opts in to [dynamic `Any`](dynamic-any.md), `json.loads()` decodes into `Any`'s
containers wherever its result becomes `Any` storage: an `Any` variable, argument or return value,
or a `list[Any]`, `dict[str, Any]` or `list[dict[str, Any]]`, which have `Any`'s layout there.
`json.dumps()` encodes a value that holds `Any` values, and a display or comprehension passed to
it, by walking `Any` values. Both are lib's `_pystachy_json_any.py`, which the compiler calls for
`json`'s functions in such a module (#779). The document is then one set of objects that typed
code (`dict[str, Any]`, `list[dict[str, Any]]`) and `Any` code share, with no copy: a change made
through either shows through the other (`tests/programs/inference/dynany_json.py`,
`tests/programs/inference/dynany_json_app.py`).

The dynamic `loads()` and `_raw_decode()` paths preserve integer tokens beyond signed
64-bit range as Python `int` values. The scanner retains its small-integer fast path and
fixed-width indices; only an overflowing token crosses into a promoting-integer helper.
The calling module does not need a `python-int` pragma. Conversion retains the runtime's
4,300-digit limit and raises `ValueError` when it is exceeded. Typed `JSONValue` and the
public `JSONDecoder` methods retain their signed-64-bit boundary.

`dumps()` of `Any` values writes tuples as arrays, and int, float, bool and `None` keys as
strings, and takes CPython's `skipkeys`, `check_circular`, `default` and `indent` too. It raises CPython's
`TypeError`s: `Object of type C is not JSON serializable` for a value JSON cannot hold, and `keys
must be str, int, float, bool or None, not C`. It preserves wide integer values and
keys; its other limits are those listed above.

A `default` callback's result must be representable as `Any`. Annotate it `-> Any`
when it returns dynamic containers; concrete results such as `int` and native
`list[int]` also work. An existing `dict[str, int]` result is rejected; use dynamic
dictionary storage. See the [typed/dynamic contract](dynamic-any.md#the-typeddynamic-contract).

Without `sort_keys`, callbacks that delete and reinsert keys or clear and repopulate the dict
can change output order or entries compared with CPython's live dict-table traversal (the
[dynamic `Any` deviation](dynamic-any.md#selecting-dynamic-storage)).
Elsewhere, including where the result has a typed or no annotation (`doc = json.loads(s)`),
`json`'s own functions and `JSONValue` storage stay as they are.

## Decoder

### Scanning

`loads()` scans UTF-8 bytes with integer comparisons, avoiding one-character
strings and code-point translations during scanning. Object keys, and strings
in a document of at most 1 KiB, use a scalar loop with no per-string setup.
In a longer document, a string value of more than 32 bytes
continues past that scalar prefix with a shared bounded byte scanner, skipping eight
bytes at a time until a quote, backslash or control byte is possible, then checking
the matching word and tail scalar.

After an escape, the helper scans the next ordinary
run when the run before the escape reached 16 bytes; dense escapes keep the byte loop,
which a per-byte bound check made mispredict. Both typed and dynamic decoders use
this scanner. Loads use `memcpy`, require a complete word inside the range and
accept any alignment.

Short texts and keys retain the scalar loop because scanner setup costs more than
it saves there. The [JSON decoder controls](../bench/smoke/README.md#retained-json-decoder-controls)
and [byte-scanning controls](extended-performance.md#json-byte-scanning-controls)
measure both short and long inputs.

### UTF-8 and error positions

Pystachy's `str.encode()` returns the string's own UTF-8 storage unless
the text contains a character from U+D000 to U+DFFF; then it checks and copies
every character. Every delimiter, digit and escape is ASCII, so the scanner stops
only at character boundaries. Errors convert byte offsets into the character
positions CPython reports.

A string without escapes is one slice of the bytes, decoded without an error
handler or codec lookup. A document containing lone surrogates, which `encode()`
rejects, decodes its slices with `surrogatepass`.

Pystachy reads files
([deviation](language/compatibility.md#text-and-file-positions)), `input()` and
`sys.argv` without checking their bytes, and `encode()` returns such text
unchanged. When a slice is not UTF-8, `loads()` parses the text again and takes
each string from the `str` itself, at character offsets counted as `str` counts
them. This preserves the earlier character-by-character decoder's behavior.

### Keys and numbers

A 64-entry cache indexed by key length and first byte, and checked byte for
byte, returns the string of an equal object key seen earlier in the same
document. Records of one shape then share their key objects, as CPython's
decoder memo makes them do, and dictionary insertion reuses those keys' cached
hashes. The cache lives for one `loads()` call.

Integer tokens of up to 18 digits accumulate directly. Longer tokens are checked
against the signed 64-bit bound: typed JSON rejects overflow, while dynamic JSON
passes an overflowing token to the promoting-integer helper.

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

In the [19 October 2026 encoder measurements](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/native-json-encoder-2026-10-19.md),
AOT and JIT `dumps()` of 5,000-record documents took 1.1–1.6 times CPython's C
encoder time. Escaping non-ASCII text with `ensure_ascii=True` was the slowest
case. The report includes inputs, measurements and comparisons with the earlier encoder.

## Benchmarks

[`tools/bench_json.py`](../tools/bench_json.py) measures parsing, processing and
encoding of nested API/event records. It runs the same
[`bench/json_records.py`](../bench/json_records.py) consumer in each mode and checks
every measured result against CPython. Run the controller with the exact CPython
version in [`.python-version`](../.python-version), from the repository root:

```sh
python3.13 tools/bench_json.py --compiler ./pystachy --smoke
python3.13 tools/bench_json.py --compiler ./pystachy --profiles skewed --records 10000
python3.13 tools/bench_json.py --compiler ./pystachy --pypy /path/to/pypy3 \
  --modes cpython pypy jit aot cpython-lib pypy-lib --texts utf8 ascii escaped
```

`--smoke` checks correctness with 100 records and one iteration, sample and process;
its timings are not speedup evidence. Use `--compiler "python3.13 -m pystachy"` for
the CPython-hosted compiler. Reports go to `build/json-benchmark.json` by default;
`--json PATH` selects another file.

The consumer also runs without arguments: it prints one deterministic checksum
for a small fixture covering every amount alternative, missing fields and nested
Unicode. `make bench` and the verification matrix compare that output with
CPython in JIT and AOT. The controller supplies the larger measurement inputs.

### Runtimes

| Mode | JSON implementation | Execution |
|---|---|---|
| `cpython` | CPython's standard `json`, including its C scanner | Interpreter |
| `pypy` | PyPy's standard `json` | PyPy interpreter and tracing JIT |
| `jit`, `aot` | The compiler-resolved `json.py`, normally `lib/json.py` | Pystachy native code |
| `cpython-lib` | That same `json.py` source | CPython interpreter |
| `pypy-lib` | That same `json.py` source | PyPy interpreter and tracing JIT |

The `-lib` modes separate the parser implementation from how it executes. For
PyPy 3.11, the controller replaces the PEP 695 type-alias statement with an
assignment in a temporary copy; it leaves the parser logic unchanged.

The controller verifies each imported JSON module with `bench/` first on the
interpreter's module path. Native resolution checks `bench/`, then `PYSTACHY_PATH`
entries relative to the repository root, then `lib/` under `PYSTACHY_HOME` or the
compiler's home. The report records the resolved source path and hash. To compare
parser revisions with one compiler, select their directories through
`PYSTACHY_PATH` and keep the other inputs fixed.

### Inputs and phases

Inputs are deterministic and generated outside the timers. `skewed` uses integer
amounts in 92 of each 100 records; `mixed` has no integer amounts; `changing`
switches from skewed to mixed halfway through. Floats, nulls, missing fields,
strings, booleans and container amounts all affect the checksum. The inputs also
contain nested objects, arrays and Unicode; their sums stay within signed 64-bit
range.

`--texts utf8` keeps raw non-ASCII text, `escaped` encodes the same values with
`\u` escapes, and `ascii` substitutes one ASCII character for each non-ASCII
character. The ASCII control preserves character lengths and the processing
checksum.

| Phase | Separately timed operations |
|---|---|
| `all` | Parse; process the parsed document; parse and process together |
| `predecoded` | Process a document decoded before timing; rebuild its containers; encode it with default `json.dumps()` options |

Both phases run by default; `--phases` selects either. The `predecoded` processing
measurement excludes parser allocation and garbage. Its `rebuild()` control
creates fresh lists and dicts around the same scalars and strings, without text
scanning or conversion. In native code, use `parse - rebuild` as an optimistic
ceiling on savings from a faster input format that still builds these containers.
That subtraction is not valid for CPython, where `rebuild()` is interpreted and
the standard decoder runs in C. Encodings must preserve the decoded checksum and
match CPython's text length and order-sensitive digest.

Every case compares `generic` processing with `handguarded`, a handwritten integer
fast path that excludes booleans and falls back for every other value. It reads
the original objects without copying them or persisting a schema. This is a
source-level control; it neither collects profiles nor demonstrates automatic
compiler specialization. LLVM may optimize the generic path similarly, so the
guard need not improve performance.

### Measurement and evidence

Warmup runs the measured operations for `--warmup-ms` (2,000 ms by default), with
at least one round even when set to zero. Samples exclude warmup, and the report
retains its duration and round count. PyPy may compile during warmup; Pystachy
compiles before the program starts.

Operation timers exclude file I/O, initial validation and printing. Whole-process
wall time includes those costs, warmup and JIT compilation. AOT build time and
executable size are separate, as is the first native invocation that primes the
runtime cache. The independent `PYSTACHY_GC=stats` run reports GC and heap data,
not an allocation count. On Linux, `/usr/bin/time` supplies peak RSS when present;
otherwise RSS is `null`. JIT and build RSS include toolchain children and are not
comparable with AOT runtime RSS.

Reports retain raw samples, input and source hashes, interpreter identities and
binary hashes, imported JSON paths, compiler revision, environment and dirty-tree
status. Mismatched checksums or encodings and malformed timing output fail the
run; the report retains completed work with a failed status. Compare completed,
passed runs.

Independent processes are the statistical repetitions. The controller rotates
execution order, takes the median of each process's samples, then summarizes
those process results. For performance evidence, increase `--processes`,
`--samples` and `--iterations` on an idle host. Keep benchmarks separate from
builds and test suites that compete for the same resources.

### Earlier measurements

The [18 October parser measurements](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/native-json-parser-2026-10-18.md)
compare CPython, PyPy and Pystachy with parsing and processing timed separately.
They did not establish a reliable benefit from the handwritten guarded path in
JIT or AOT. The [initial checkpoint](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/native-json-2026-10-18.md)
retains the earlier parser baseline and experiment details. These reports describe
their pinned revisions; use the commands above to measure the current tree.

## Validation and reproduction

Use the pinned CPython from `.python-version` and the documented LLVM toolchain.
From the repository root:

```sh
PYSTACHY_GC_STRESS_PROGRAM=1 make test-py PY=python3.13 FILES="tests/programs/library/json_*.py tests/programs/inference/recursive_alias_*.py tests/deviations/json_*.py tests/deviations/recursive_alias_limits.py"
python3.13 tools/json_check.py --native --gc-stress
```

The regular fixtures compare against CPython's standard `json`; the separate
[JSON limit fixture](../tests/deviations/json_limits.py) records deliberate integer
and `dump()` depth differences. The [runtime limit fixture](../tests/deviations/recursive_alias_limits.py)
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
