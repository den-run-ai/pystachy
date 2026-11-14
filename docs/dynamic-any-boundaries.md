# Dynamic library boundaries

Apply the [admission rule](dynamic-any.md#admission-and-containment) to each
storage or operation boundary, not to a whole library name. An opted-in module
can contain mostly concrete code. This inventory covers the shipped `lib/` and
maintained `ports/json_repair/` opt-ins, rather than tests that intentionally
exercise dynamic behavior. An ordinary generic helper can also specialize to a
dynamic argument type supplied by its caller; this is a local opt-in inventory,
not a complete value-flow graph.

`make check-fast` runs the
[inventory test](../tools/test_dynamic_any_inventory.py). Using the compiler's
pragma rule, it fails when a `lib/` or `ports/` module opts in without exactly one
row here, or a row names a module that does not opt in. It checks completeness
only; reviewers still judge each row's reasoning.

The retained contracts below describe why silently replacing existing storage
would change behavior. They do not prove that every current annotation or
implementation choice is necessary. Compiler limitations and removable internal
state are listed separately. No new restriction on existing callers is implied.

## Library modules

| Module | Consumer and retained open boundary | Concrete work and remaining containment debt |
|---|---|---|
| `tomllib._parser` | `loads()` returns mutable tables/arrays whose values may contain arbitrary supported `parse_float` results. Preserve callback order, returned object identity, shared objects and existing runtime errors. | Namespace flags are typed recursive nodes with integer sets. Positions, keys, string scanning and errors are concrete. A generic recursive value type could serve closed consumers, but cannot silently replace the existing mutable output storage. |
| `tomllib._re` | `match_to_number()` returns either an integer or the supplied callback's object. A single callback may itself return different supported types. | Regex/date helpers already have concrete annotations. Specializing a known callback to `int \| T` still needs accepted-program and numeric-identity parity; closed-union inference alone does not establish it. Moving the callback function leaves transitive identity tracking in place. |
| `tomllib._types` | `ParseFloat = Callable[[str], Any]` defines the current dynamic callback result contract. | `Key` and `Pos` are concrete. Removing this pragma changes the alias's meaning in its consumers; an alternative generic alias requires their coordinated migration. |
| `logging` | Stored messages, arguments, extra/default values, filters and replacement records expose open payloads and callbacks. Runtime formatting invokes their supported conversion methods. | Formatting mechanics and normalized record fields should stay concrete. Level inputs have a known normal set, but invalid values must keep their existing validation timing. The historical `Filterer.filter` comment predates closed unions; its false-or-record result deserves a separate checked migration. |
| `_pystachy_percent` | Logging and argparse runtime formats select values from heterogeneous argument packs or mappings, invoking their conversions and preserving error order. | Scanner offsets, flags, widths, precision and output strings are concrete. A runtime-sized open argument pack is distinct from a statically specialized tuple. |
| `_pystachy_json_any` | Dynamic `json.dumps` supports open objects through `default`, tuple inputs and mutable heterogeneous graphs; dynamic `loads` returns containers callers may mutate through `Any`. | The scanner already uses typed `json._Parser` and the checked `identity-inert` hint. Closed consumers can use `JSONValue`. Preserve wide integer behavior separately from this storage choice. |
| `pathlib` | Current path entry points validate supported path/string/sentinel inputs at runtime and preserve path class/subclass behavior. | The bounded path input set is substantially compiler/inheritance debt, not inherently open. Constructor specialization must not turn the base into an unusable generic class, lose subclasses or reject invalid inputs earlier. Path text and scanning stay typed. |
| `threading` | Thread/Timer retain arbitrary supported targets, argument packs and keyword packs; Condition retains a supplied lock implementing its supported protocol. | Thread's nongeneric base requirement is compiler debt. Names after conversion, counters, waiters and normalized lock state can be concrete. Preserve existing constructor errors; this inventory adds no thread execution support. |

## JSON repair port modules

All paths below are relative to `ports/json_repair/`. Parsed JSON data has a
closed mathematical value set; the current mutable output API and its callers
can have a broader storage contract. Prefer a typed implementation for a closed
consumer only after preserving its aliases and the boundary to existing users.

| Modules | Current boundary | Concrete work and remaining containment debt |
|---|---|---|
| `json_repair.py`, `json_parser.py`, `parse_array.py`, `parse_object.py`, `parse_string.py`, `parse_comment.py`, `parse_string_helpers/parse_json_llm_block.py` | Dynamic repaired results, nested mutable containers, optional result/log tuples and interoperability with dynamic JSON. | Scanning state is largely concrete already. Recursive typed storage and known log-record fields are candidates; returning logs through an existing `Any` tuple is an alias/layout boundary to preserve. |
| `parse_number.py` | Returns numbers or delegated parsing results to its parent. Promoting integers independently preserve large JSON integers. | Number scanning is concrete. Delegation can return broader results than an int/float/string union; specialize only after following those paths. |
| `utils/object_comparer.py` | Recursively compares existing heterogeneous repaired graphs and accepts supported `Any` inputs. | A closed JSON specialization may coexist with the open helper; narrowing existing callers requires evidence. |
| `parser_parenthesized.py`, `parse_string_helpers/parse_boolean_or_null.py`, `parse_string_helpers/object_value_context.py`, `utils/json_context.py` | These helpers operate on inferred parser objects; they declare no `Any` annotation. | Their local pragmas are removable candidates, subject to mixed-display and inference checks. Context-stack state is known int/bool/None storage. Pragma deletion alone does not remove imported identity tracking. |
| `__main__.py` | The CLI serializes the repair result; it declares no `Any` annotation. | Check encoder dispatch before removing its opt-in. A smaller pragma count is not a cost result. |
| `__init__.py`, `utils/__init__.py`, `parse_string_helpers/__init__.py` | Re-exports or package documentation; no dynamic storage originates here. | Local opt-ins are hygiene candidates, with no independent performance claim. |

## Evidence required for a migration

Keep public output layouts and mutable aliases stable, including callbacks that
return the same object repeatedly. Check callback timing and exceptions before
and after malformed input, and same-object NaN membership/equality where numeric
identity can be observed. Pair behavioral checks with an emitted representation
assertion that fails on the old implementation; fewer source annotations alone
are not sufficient.

TOML's typed flag tree is covered by the [table/error cases](../tests/programs/library/lib_tomllib_flags.py),
[open callback cases](../tests/programs/library/lib_tomllib_boundary.py),
and the TOML checks in [identity-scope tests](../tools/test_identity_scope.py).
The [ordinary typed-callback consumer](../tests/programs/library/lib_tomllib_typed_callback.py)
also observes the identity of the imported helper's result without opting in to
dynamic `Any`. A generic `int | T` replacement currently rejects its `is` comparison
when `T` is `float`; this is closed-union operation debt, not failed generic inference.
The [consumer benchmark](../bench/toml_boundary/README.md) separates raw and
optimized program IR, hosted compilation, JIT/AOT execution, AOT allocation
requests and conservative post-collection live bytes.

The flag-tree change reduces dynamic operations inside typed parser state. It
does not change the compiler's module dependency closure or full-tracking
fallback. The regex and date modules that TOML imports now keep numbers as
values, as CPython's C implementations do
([numeric-value modules](dynamic-any.md#numeric-value-modules)): they no longer
track identity in either case. TOML's own modules, `functools` and `string`
still do. Preserve existing ordinary-mode IR/diagnostics and
library consumers throughout that work; do not claim that all remaining opt-ins
are unavoidable.
