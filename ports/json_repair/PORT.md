# json_repair: in-memory repair

Adapted from [json_repair v0.64.1](https://github.com/mangiucugna/json_repair/tree/v0.64.1),
commit `ace9b23cb7fc6757775d5fafbfaaa9a88363a573`, by Stefano Baccianella and contributors
under the [MIT license](LICENSE). Pristine files were committed before adaptation;
[the manifest](../../tests/upstream/json_repair/manifest.json) pins their SHA-256 hashes.

This bounded port is included in the `pystachy-ports` wheel.
It repairs individual strings into native heterogeneous Python values.
It uses Pystachy's opt-in dynamic `Any` for recursive JSON values and repair logs,
and static types for parser state and lookahead caches. There is no CPython embedding.

## API and scope

```python
# pystachy: dynamic-any
from typing import Any
from json_repair import loads, repair_json

value: Any = loads('{tool: "search", arguments: [true, null, 3,],}')
value['arguments'].append({'ok': False})
print(repair_json('{message: "hello",}'))
```

Set `PYSTACHY_PATH=ports` for JIT/AOT and `PYTHONPATH=ports` for CPython.
`repair_json` supports `return_objects`, `skip_json_loads`, `logging`,
`stream_stable`, `strict` and `ensure_ascii`. Its last three options are keyword-only:
upstream's intervening file arguments are excluded, so positional calls cannot
silently change meaning. `loads` supports the corresponding parsing options.
Schema/Pydantic, file wrappers, CLI, other `json.dumps` options and the
`JSONReturnType` export are outside this subset and are not advertised as supported.

The default valid-JSON fast path is retained, including wide integer tokens, decoded
surrogate pairs and CPython's nonfinite-number extensions. This port preserves most
upstream heuristics, including undesirable behavior: truncated `fal` becomes a string;
repeated top-level objects can replace earlier objects; duplicate keys can use
the last value; malformed escaped emoji can remain two surrogate characters.
Forced repair (`skip_json_loads=True`) can discard standalone primitive roots, as
can a primitive surrounded by comments/prose. Keep the default decoder path for
valid scalar documents. Comments inside arrays and between an object colon and its
value are consumed before parsing the actual value, fixing upstream value loss.
Split trace records before repair and validate types and content afterward.

## Adaptations

- Remove schema-only branches and file/CLI interfaces. Preserve in-memory parsing
  branches and upstream repair rules.
- Use explicit `Any`, `list[Any]` and dynamic dictionaries instead of the imported
  recursive alias; omit forward parser annotations so helper functions specialize
  on their concrete parser argument.
- Represent the private context enum with integer constants; unwind deferred
  contexts explicitly with `try/finally` instead of unsupported `ExitStack`.
- Guard `log()` with the logging flag instead of replacing a bound method.
- Spell literal-return annotations as `bool`/`str`, add optional-character
  narrowing, and spell the fixed delimiter tuple explicitly.
- Encode ordered string targets with `repr(list_of_targets)` for cache keys:
  boxing a variable-length typed tuple into `Any` is unsupported. The key remains
  injective for these string lists; this adds allocations and is not a speed claim.
  Cache values use `tuple[int, int | None]` instead of `Any`.
- Use `str.find` for single-character lookahead with the same escape boundaries;
  retain the original scan for other targets and negative offsets.
- Update brace/bracket state incrementally after replacing a trailing escape,
  preserving decoded structural characters without rescanning accumulated text.
- Accumulate string content in bounded 64-code-point tails and immutable chunks;
  cache tail/regex whitespace metadata and flatten once at finalization. This
  removes repeated growing-prefix copies. The [accumulator report](../../bench/json_repair/ACCUMULATOR.md)
  records native wins, a warmed PyPy mixed-workload regression and higher CPython
  peak memory; this remains an experimental port tradeoff.
- Process ordinary repair text in spans between quotes, escapes and structural
  characters, retaining the existing heuristics at each boundary. Append source
  ranges in bounded chunks; the same storage helper serves decoded escapes and
  inline-container content. Positions and whitespace decisions remain based on
  Unicode code points. This is a port optimization using existing string
  operations, independent of the native JSON decoder's byte scanner.
- Use the native `json._raw_decode` adapter at two call sites, with a guarded
  import falling back to CPython’s `JSONDecoder`. The public decoder keeps its
  class identity; see the [JSON API notes](../../docs/json.md).
- Skip comments while still expecting an array item or object member value,
  without recursive calls for consecutive comments. Top-level comments resume
  the main parse loop, so alternating comments and discarded prose do not grow
  the native stack either.

The string-repair implementation remains upstream's roughly 900-line heuristic
parser. Changes are marked with `Pystachy port` comments or described above.

## Validation and limits

The [replay corpus](../../tests/upstream/json_repair/README.md) contains **645**
input/API/option combinations, with type-sensitive comparisons, dictionary order,
exact Unicode codepoints, serialized output, logs and error messages. It is not
the complete upstream suite. The checker retains all cases and fails on every
mismatch; it does not silently waive known limitations.

On CPython 3.13.16, pristine upstream and adapted sources match **645/645**.
Native JIT, AOT and both modes with collection at every allocation now match
**645/645**. That corpus did not detect
wide primitive-root loss, Unicode/strict-mode changes after overflow fallback or
comment-related value loss. Additional differential regressions now cover those
cases, independently of the retained upstream oracle. The dynamic native JSON
decoder promotes a wide token directly, so valid documents keep the normal
decoder's semantics instead of entering heuristic repair; the facade and both
`raw_decode` probes keep upstream's exception handling. The number parser
combines dynamic `Any` with promoting integers; parser indices stay fixed-width.

Valid input takes the default fast path, `json.loads()`, whose nesting counts against
the native recursion limit: at the default limit, about 500 nested containers decode and
return as upstream does on CPython (#1021), and deeper valid input raises
`RecursionError` from the fast path, whereas CPython's C decoder accepts up to 9,998 at any
limit. Under a raised limit the codec stops at 2,000 containers with CPython's message
([deviation](../../tests/deviations/json_limits.py)).
Malformed-input repair has no separate depth budget: exceeding the native
recursion limit raises `RecursionError`, which the facade translates to upstream's
`ValueError("Input nesting exceeds the supported parser recursion depth.")`. At the
default limit, native JIT and AOT repair the same maximum array, object and
array-of-object nesting as upstream on CPython 3.13.16 (arrays one level deeper);
see the [native recursion policy](../../docs/language/compatibility.md#errors-and-control-flow)
for frames that do not count. Integer tokens beyond the runtime's 4,300-digit
conversion limit follow upstream: valid-JSON decoding falls back to repair, the
missing-brace probe declines, and the number parser keeps the token as a string,
so forced repair can drop such a top-level number. Forced-repair primitive-root
heuristics described above remain. The replay establishes these 645 cases, not
full-package parity.

The small [native regression](../../tests/programs/apps/port_json_repair.py)
checks mutable `Any` results, repair behavior, Unicode and the fast path. Run:

```sh
make test FILES='tests/programs/apps/port_json_repair*.py tests/programs/library/json_raw_decode.py tests/programs/inference/dynany_json_raw_decode.py'
```

See the replay README for the complete corpus commands and original input provenance.

See the [performance report](../../bench/json_repair/PROFILING.md) for historical typed-cache
measurements, payload scaling and bottlenecks, and the
[bounded-accumulator report](../../bench/json_repair/ACCUMULATOR.md) for the refreshed
integrated baseline, copy-work evidence and current cross-engine tradeoffs. The [completion report](https://github.com/den-run-ai/pystachy/blob/06e3ad5d08514ba31fb231fe4636a962fe6578e3/docs/reports/json-repair-port.md)
records validation and the minimal upstream contribution strategy.
