# json_repair

[json_repair v0.64.9](https://github.com/mangiucugna/json_repair/tree/v0.64.9), commit
`36d7a6ed53e777b5a5b9017e33d35ea2af8b7c6e`, by Stefano Baccianella and contributors under the
[MIT license](LICENSE), with a small patch set.
[The manifest](../../tests/upstream/json_repair/manifest.json) pins the SHA-256 hashes of
upstream's 22 source files.

This port is included in the `pystachy-ports` wheel. It repairs strings, files and streams
into native heterogeneous Python values, with no CPython embedding. It uses Pystachy's opt-in
dynamic `Any` for JSON values and repair logs, and static types for parser state.

Until 0.64.8 the port was a schema-free rewrite: 2,671 of its lines differed from upstream.
It is now upstream's source: 678 lines differ from 0.64.9, of which 208 are the
[string scanner](#performance), 51 the [command](#file-and-pipe-command) and 116 the body of
upstream's `cli()`, which is in [a module of its own](#imports) with two lines changed. Twelve
modules differ only by their opt-in comments, and `utils/string_file_wrapper.py` not at all.
The port adds one package, [a JSON Schema validator](#schema-guided-repair) of 1,003 lines, in
place of the `jsonschema` package. Its behavior is upstream's; a difference that this page
does not list is a bug.

## API and scope

```python
# pystachy: dynamic-any
from typing import Any
from json_repair import from_file, load, loads, repair_json

value: Any = loads('{tool: "search", arguments: [true, null, 3,],}')
value['arguments'].append({'ok': False})
print(repair_json('{message: "hello",}', sort_keys=True))
print(from_file("broken.json"))
schema: Any = {"type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"]}
print(loads('{count: "3", note: "x"', schema=schema))  # {'count': 3, 'note': 'x'}
```

Set `PYSTACHY_PATH=ports` for JIT/AOT and `PYTHONPATH=ports` for CPython.

The package exports upstream's names with upstream's signatures: `repair_json`, `loads`,
`load`, `from_file` and `JSONReturnType`. `repair_json` takes `return_objects`,
`skip_json_loads`, `logging`, `json_fd`, `chunk_length`, `stream_stable`, `strict`, `schema`,
`schema_repair_mode` and `json.dumps()` keyword arguments. The native `json.dumps()` takes
`ensure_ascii`, `allow_nan`, `sort_keys`, `separators`, `indent`, `skipkeys`, `check_circular`
and `default`; it has no `cls`.

The port keeps upstream's heuristics, including the ones that surprise: truncated `fal`
becomes a string; repeated top-level objects can replace earlier objects; duplicate keys can
use the last value; malformed escaped emoji can remain two surrogate characters; forced
repair (`skip_json_loads=True`) can discard a standalone primitive root; a stray slash at the
start of an array item or object value drops what follows it (`[/1,2]` repairs to `[2]`).
Split trace records before repair and validate types and content afterward.

For accelerated calls from CPython, build the
[native companion module](../../examples/json_repair/README.md).

Native repair uses CPython 3.13's Unicode 15.1 character classification, including non-BMP
letters and the distinct decimal, digit and numeric classes.

## Differences from upstream

Each difference is marked `Pystachy port` in the source.

### Schema-guided repair

A JSON Schema dict or a boolean schema guides repair natively, in both repair modes:
[schema_repair.py](schema_repair.py) and [parser_schema.py](parser_schema.py) are upstream's,
with the changes [the compiler needs](#types-the-compiler-needs).

Upstream validates with the optional `jsonschema` package, which no native program can
import. The port validates with its own [validator](_jsonschema/validators.py), natively and
under CPython, also where `jsonschema` is installed. It follows jsonschema 4.26 keyword by
keyword for drafts 4, 6, 7, 2019-09 and 2020-12: what each keyword accepts, the order in which
a schema's keywords are tried, and each message, so that a repair fails with upstream's
`ValueError`. A schema is checked against [its draft's metaschema](_jsonschema/_metaschemas.py)
before any repair, and an invalid one raises upstream's `Invalid schema: ...`.

What the validator leaves out fails; nothing is accepted unchecked:

- **References.** `$ref`, `$dynamicRef` and `$recursiveRef` resolve `#` and `#/...` pointers
  into the root schema, also through the root's own `$id`. An anchor (`#name`), another
  document, and a reference inside a subschema that has an `$id` of its own raise
  jsonschema's `_WrappedReferencingError` with `Unresolvable: REF`, where jsonschema may
  resolve them (it fetches remote schemas). Upstream's repair itself resolves only `#/...`.
- **Draft 3.** A schema that declares it raises `Invalid schema: Draft 3 schemas are not supported.`
- **Formats.** `format` is asserted only while a schema is checked, and only `regex`, as with
  `jsonschema` installed alone. `pattern` and `patternProperties` use the native
  [`re`](../../lib/compatibility.md).
- **Order.** Upstream iterates two sets of names in an order that the hash seed decides: an
  object's additional properties (jsonschema) and a schema's required names
  (`parser_schema.py`). The port uses the instance's order and the schema's. This decides
  which of several errors is reported, the order of missing names in one, and the order of
  the properties that salvage mode fills.
- **Schema models.** No native program can import `pydantic`, or a module by its name. A
  model passed as `schema` is rejected as any value that is no schema, and
  `load_schema_model()` (`--schema-model`) raises
  `pydantic is required when using schema models.`, also under CPython where pydantic is
  installed.

### Files and streams

`load()`, `from_file()` and `json_fd` buffer the stream's text, as upstream does for a stream
that cannot seek, in place of upstream's chunked `StringFileWrapper`. A seekable file keeps
upstream's file behavior: it does not probe a valid JSON value after a prefix. `chunk_length`
is accepted and has no effect. `utils/string_file_wrapper.py` is upstream's file, which the
port's parser does not use; its `seek()` and `tell()` do not compile natively.

### Imports

Upstream's `json_repair.py` imports `argparse` and `pathlib` for its command and for
`from_file()`'s `Path`, and its parser compiles two regular expressions. A native program
compiles what it imports: with those, a program that only repairs a string loaded 48 modules
where the earlier port loaded 24, took three times as long to compile, was twice the size and
started 7% slower, two thirds of its code being the `re` engine. The port loads none of them:

- `cli()` is in [_cli.py](_cli.py), unchanged but for two lines (the schema it loads is
  declared `Any`, and the output path has a `""` alternative for its type).
  `json_repair.json_repair.cli()` imports that module where it runs, as CPython allows any
  function; natively, a program that runs the command imports `json_repair._cli` itself.
- `Path` is imported for type checking only, `from_file()`'s annotation is quoted, and the
  file is opened with `open(str(filename))`, as `Path(filename).open()` opens it.
- Upstream imports `jsonschema` where a schema is used. A native function imports only what
  module-level code loads, so `schema_repair.py` imports the port's validator, and the
  validator `re`, as it loads. A program that repairs without a schema carries both: see
  [the cost](#what-schema-support-costs-a-program-without-a-schema).
- `parse_json()` scans for the characters of upstream's two patterns, `[{\[(#/]` and that set
  with the string delimiters, in place of `pattern.search()`.

### Types the compiler needs

- Every module opts in to dynamic `Any` with `# pystachy: dynamic-any`; `parse_number.py`
  also opts in to promoting integers.
- `JSONParser.log` is declared `Callable[[str], None]`, the one type of the bound method and
  the no-op lambda that upstream assigns it.
- The repair log is a `list[Any]`: a typed `list[dict[str, str]]` cannot be returned through
  an `Any` value.
- The two `json.JSONDecoder().raw_decode()` results are declared (`value: JSONReturnType`,
  `end_idx: int`), which selects `Any` storage for the decoded value
  ([JSON API notes](../../docs/json.md)).
- The lookahead cache has string keys: a runtime-length tuple is no dict key. A single
  character is its own key, two or more single characters are a NUL and those characters, and
  other targets are the `repr()` of their list. A scalar and its singleton list share an
  entry, as upstream's tuples do.
- In `schema_repair.py`: the two `json.loads()` results are declared `Any`, as above. A
  schema's list of types is a `list[Any]`, and the container class that a decoded string must
  be is an `Any` value compared with `type(x) is`, where upstream has `list[str]`,
  `type[object]` and `isinstance()`. The cached schema check returns `True`: a cache of
  `None` results has no type. One `dict(value)` is `value.copy()`, where the compiler loses
  that `value` is a dict. The module imports `json_repair.json_repair` by name where upstream
  calls `importlib.import_module()`, and it and the validator opt in to promoting integers.
- `parser_schema.py` keeps a schema's required names in a list, in the schema's order, where
  upstream has a set ([order](#schema-guided-repair)).

### Performance

These keep native repair linear and within reach of the hand-written port they replace. None
changes a result.

- **String scanning** ([parse_string.py](parse_string.py), 208 lines). String content
  accumulates in bounded 64-code-point tails and immutable chunks, with cached length, last
  character and whitespace metadata, and is flattened once. Ordinary text is appended in
  spans between quotes, escapes and structural characters, and a run of simple control
  escapes is decoded in one pass when logging is off. Upstream 0.64.9 reaches linear time
  another way, with a list of characters and a regular expression for plain runs; natively
  that was about 2 to 8 times slower on long strings than this module in informal checks. Its lookahead reuse
  (`_array_quotes_pair_up`, cached `skip_to_character` calls) is taken as it is.
- **Comments** ([parse_comment.py](parse_comment.py)). `skip_comment()` finds a line
  comment's earliest terminator in bounded windows and a block comment's closing delimiter
  directly, and slices the log text only when logging. Upstream builds the comment one
  character at a time. For a block comment that was quadratic natively until
  [an append stayed in place](../../docs/performance.md) through `endswith()`. It is linear
  now and still the slower: in an informal check, a repair with an 80,000-character comment
  took 1.3 ms with upstream's module and 0.03 ms with this one, and one with a 400-character
  comment 13 µs and 5 µs.
- **Root scan** ([json_repair.py](json_repair.py), [json_parser.py](json_parser.py)). Where
  `json.loads()` rejected the document for a reason other than extra data, or the document
  starts with a bare object key, the parser does not scan the whole first root again to
  decide whether a valid JSON value might follow it.
- **Schema paths** ([parse_array.py](parse_array.py), [parse_object.py](parse_object.py)).
  The path of an array item or object member is formatted only with a schema.

The comment, root-scan and schema-path changes also save work under CPython and are
candidates for upstream. The string module is not: under CPython upstream's is faster.

#### What schema support costs a program without a schema

A native program compiles what it can reach, and `repair_json()` reaches the schema modules,
the validator and `re` whether or not a schema is passed. For a program that repairs one
string, against the port before schema support, with one compiler: repair itself is unchanged
(0.993 to 1.010 times the instructions on the ten
[benchmark workloads](../../bench/json_repair/README.md)); it starts in 723,491 instructions
against 702,242 (3.0% more, `re` being 12,852 of them); its executable is 1,243 KB against
567 KB; its typed IR is 168,355 lines against 48,781, from 43 modules against 31, and takes
1.1 s to produce against 0.4 s.

## File and pipe command

Run from the repository root.

```sh
PYSTACHY_PATH=ports ./pystachy build examples/json_repair/repair.py -o /tmp/json_repair
/tmp/json_repair input.json --output repaired.json
printf '{name: "café",}' | /tmp/json_repair --ensure_ascii
PYTHONPATH=ports python3 -m json_repair --help
```

[__main__.py](__main__.py) is the port's own command. It accepts a filename or stdin and
writes to stdout, `-o/--output TARGET`, or the input file with `-i/--inline`. It reads the
full input before repair and serializes the result before opening the output file.
`--skip-json-loads`, `--strict` and `--ensure_ascii` use the corresponding parser and encoder
options. The command requires valid UTF-8 input and output. A lone surrogate in a JSON escape
needs `--ensure_ascii`. A decoding or encoding error leaves the destination untouched. Output
is single-line JSON with a trailing newline only on stdout. Argument errors exit 2. File and
repair errors exit 1.

Upstream's own command also compiles natively: `json_repair._cli.cli()`
([imports](#imports)), with its indented output and its `--indent`, `--schema` and
`--schema-repair-mode` options. The
[native regression](../../tests/programs/apps/port_json_repair_schema.py) compares it
with CPython; 19 invocations, the schema ones apart, matched pristine upstream's output,
status and files in an informal check. The command above stays the port's own: it leaves the
destination untouched where a repair or an encoding fails, which upstream's does not.

Run the process-level [CLI check](../../tests/upstream/json_repair/cli.py) from the repo root
with pinned CPython and a built compiler.

```sh
python3.13 tests/upstream/json_repair/cli.py ./pystachy
```

## Validation and limits

The [replay corpus](../../tests/upstream/json_repair/README.md) contains **962** input/API/option
combinations, with type-sensitive comparisons, dictionary order, exact Unicode code points,
serialized output, logs and error messages. Pristine 0.64.9 and the port under CPython, and
the port in native JIT and AOT, with and without program GC stress, each pass all 962. The 943
cases retained from 0.64.8 have unchanged outcomes.

Upstream's own test suite runs against the port under CPython. With `jsonschema` and
`pydantic` installed, pristine 0.64.9 passes 573 tests and the port 556: 15 of the other 17
pass a pydantic model, and 2 read the string scanner's accumulator state. A
[differential fuzz](../../tests/upstream/json_repair/README.md#differential-fuzz)
of 1,000,000 generated schema-free cases, with text placed at the boundaries of the string
scanner's chunks and the comment scanner's windows, found no difference between pristine
upstream and the port, under CPython or natively. Its schema family found none in 30,000
repairs under generated schemas, against upstream with `jsonschema` 4.26 and
[the two orders pinned](#schema-guided-repair), and the validator alone agrees with
`jsonschema` on 50,000 generated schemas, but for the references it leaves out. A
[native regression](../../tests/programs/apps/port_json_repair_schema.py) replays 182 of the
schema cases against upstream's recorded outcomes. The corpus and these runs establish these
cases, not full-package parity.

Valid input takes the default fast path, `json.loads()`, and returning text re-encodes the
value with `json.dumps()`. Both nest as CPython's C decoder and encoder do: up to 9,998 nested
containers at any recursion limit, and deeper valid input raises the decoder's
`RecursionError`, as upstream's does.
Malformed-input repair has no separate depth budget: exceeding the native recursion limit
raises `RecursionError`, which upstream's facade translates to
`ValueError("Input nesting exceeds the supported parser recursion depth.")`. Comments
separated by prose recurse once for each alternation, as upstream's do, and reach that error
the same way; see the [native recursion policy](../../docs/language/compatibility.md#errors-and-control-flow)
for frames that do not count. Integer tokens beyond the runtime's 4,300-digit conversion
limit follow upstream: valid-JSON decoding falls back to repair, the missing-brace probe
declines, and the number parser keeps the token as a string.

The [native regressions](../../tests/programs/apps/port_json_repair.py) check mutable `Any`
results, repair behavior, Unicode, scanning bounds and the fast path. Run:

```sh
make test FILES='tests/programs/apps/port_json_repair*.py tests/programs/library/json_raw_decode.py tests/programs/inference/dynany_json_raw_decode.py'
```

See the replay README for the complete corpus commands and original input provenance, and the
[benchmark guide](../../bench/json_repair/README.md) for measurements against the port that
this one replaces.
