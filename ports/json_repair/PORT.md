# json_repair: in-memory prototype

Adapted from [json_repair v0.64.1](https://github.com/mangiucugna/json_repair/tree/v0.64.1),
commit `ace9b23cb7fc6757775d5fafbfaaa9a88363a573`, by Stefano Baccianella and contributors
under the [MIT license](LICENSE). Pristine files were committed before adaptation;
[the manifest](../../tests/upstream/json_repair/manifest.json) pins their SHA-256 hashes.

This source-only prototype is not yet included in the `pystachy-ports` wheel.
It repairs individual strings into native heterogeneous Python values.
It uses Pystachy's opt-in dynamic `Any` for recursive JSON values, repair logs and
mixed cache entries. There is no CPython embedding or replacement repair algorithm.

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

The default valid-JSON fast path is retained. This port preserves upstream's
heuristics, including undesirable behavior: truncated `fal` becomes a string;
repeated top-level objects can replace earlier objects; duplicate keys can use
the last value; malformed escaped emoji can remain two surrogate characters.
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
- Use the native `json._raw_decode` adapter at two call sites, with a guarded
  import falling back to CPython’s `JSONDecoder`. The public decoder keeps its
  class identity; see the [JSON API notes](../../docs/json-prototype.md).

The string-repair implementation remains upstream's roughly 900-line heuristic
parser. Changes are marked with `Pystachy port` comments or described above.

## Validation and limits

The [replay corpus](../../tests/upstream/json_repair/README.md) contains **557**
input/API/option combinations, with type-sensitive comparisons, dictionary order,
exact Unicode codepoints, serialized output, logs and error messages. It is not
the complete upstream suite. The checker retains all cases and fails on every
mismatch; it does not silently waive known limitations.

On CPython 3.13.16, pristine upstream and adapted sources match **557/557**.
Native JIT, AOT and both modes with collection at every allocation match
**556/557**. The remaining case contains integer `12345678901234567890`, beyond
Pystachy's signed 64-bit range; native parsing raises `OverflowError`. This is a
known runtime limit, not exact full-package parity.

The existing native JSON codec also limits nesting to 256 containers. Unlimited
integers/depth, schema APIs and Python's exact resource-exhaustion behavior are
not established by these tests. No full repository verification or broad compiler
IR comparison is claimed for this draft.

The small [native regression](../../tests/programs/apps/port_json_repair.py)
checks mutable `Any` results, repair behavior, Unicode and the fast path. Run:

```sh
make test FILES='tests/programs/apps/port_json_repair.py tests/programs/library/json_raw_decode.py tests/programs/inference/dynany_json_raw_decode.py'
```

See the replay README for the complete corpus commands and original input provenance.

Validation used source `ce6aee5e1dc1a3c3d8e85e833746e642e2839c9a`, CPython
3.13.16 and LLVM 18.1.3 on Linux x86-64. The changed compiler reached a
665,160-line three-stage IR fixed point; runtime IR stayed at 18,709 lines.
The three focused regressions pass JIT/AOT normally and under GC stress.
The JSON loader/checker unit group passes 13 tests; repository hygiene and Ruff
pass. Full `make verify` and corpus-wide `irsame` have not been run locally.

The [small throughput workload](../../bench/json_repair/README.md) measured
0.321 s AOT versus 0.748 s pristine CPython and 0.690 s adapted CPython per
20,000 repairs (seven interleaved samples, medians). This is an advisory
measurement on ten repeated synthetic records, not a general speed guarantee.
