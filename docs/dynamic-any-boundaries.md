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
row here, a row names a module that does not opt in, or a row's status is not a
contract with a test that exists or a debt with an issue. Reviewers still judge each row's
reasoning.

Each row's status is one of two, and the test checks its form:

- **contract**: a supported caller receives or supplies an `Any` value and uses it as one, so the
  opt-in is part of the module's behavior and stays. The row links a test in which a caller
  does so; typed storage that rejected or changed that program would break the
  [ground rule](https://github.com/den-run-ai/pystachy/issues/409).
- **debt**: no caller depends on `Any`; a compiler limitation keeps the opt-in, which goes when
  the linked issue's work lands and the module's consumers print what they print now.

The retained contracts below describe why silently replacing existing storage
would change behavior. They do not prove that every current annotation or
implementation choice is necessary. Compiler limitations and removable internal
state are listed separately. No new restriction on existing callers is implied.

## Library modules

| Module | Status | Consumer and retained open boundary | Concrete work and remaining containment debt |
|---|---|---|---|
| `tomllib._parser` | contract: a caller changes a returned table through `Any` ([test](../tests/programs/library/lib_tomllib.py)) | `loads()` returns mutable tables/arrays whose values may contain arbitrary supported `parse_float` results. Preserve callback order, returned object identity, shared objects and existing runtime errors. | Namespace flags are typed recursive nodes with integer sets. Positions, keys, string scanning and errors are concrete. A generic recursive value type could serve closed consumers, but cannot silently replace the existing mutable output storage. |
| `tomllib._re` | contract: `parse_float` returns any object, kept by identity ([test](../tests/programs/library/lib_tomllib_boundary.py)) | `match_to_number()` returns either an integer or the supplied callback's object. A single callback may itself return different supported types. | Regex/date helpers already have concrete annotations. Specializing a known callback to `int \| T` still needs accepted-program and numeric-identity parity; closed-union inference alone does not establish it. Moving the callback function leaves transitive identity tracking in place. |
| `tomllib._types` | contract: the callback's result type is the caller's ([test](../tests/programs/library/lib_tomllib_dynamic.py)) | `ParseFloat = Callable[[str], Any]` defines the current dynamic callback result contract. | `Key` and `Pos` are concrete. Removing this pragma changes the alias's meaning in its consumers; an alternative generic alias requires their coordinated migration. |
| `logging` | contract: a filter calls methods of a record's message ([test](../tests/programs/library/lib_logging.py)) | Stored messages, arguments, extra/default values, filters and replacement records expose open payloads and callbacks. Runtime formatting invokes their supported conversion methods. | Formatting mechanics and normalized record fields should stay concrete. Level inputs have a known normal set, but invalid values must keep their existing validation timing. The historical `Filterer.filter` comment predates closed unions; its false-or-record result deserves a separate checked migration. |
| `_pystachy_percent` | debt: typed storage of a heterogeneous argument pack ([#487](https://github.com/den-run-ai/pystachy/issues/487)) | Logging and argparse runtime formats select values from heterogeneous argument packs or mappings, invoking their conversions and preserving error order. | Scanner offsets, flags, widths, precision and output strings are concrete. Once argument conversion has finished, padding receives only the conversion settings and strings. A runtime-sized open argument pack is distinct from a statically specialized tuple. |
| `_pystachy_json_any` | contract: callers read and change documents through `Any` ([test](../tests/programs/inference/dynany_json.py)) | Dynamic `json.dumps` supports open objects through `default`, tuple inputs and mutable heterogeneous graphs; dynamic `loads` returns containers callers may mutate through `Any`. | The scanner already uses typed `json._Parser` and the checked `identity-inert` hint. Closed consumers can use `JSONValue`. Preserve wide integer behavior separately from this storage choice. |
| `inspect` | contract: a caller operates on a default as an `Any` value ([test](../tests/programs/library/lib_inspect_any.py)) | mypyc's `get_text_signature()` (`mypyc/ir/func_ir.py`, mypy 2.4.1) gives `Parameter` a default of whatever type a compiled function declares; a parameter's default and annotation and a signature's return annotation are open payloads that `str()`, `==` and `hash()` format, compare and hash at runtime and that callers read back by identity (`default is Parameter.empty`). A class template would make `Parameter` one type per default type, which a `list[Parameter]` and a `Signature` cannot mix, and a closed union cannot hold the marker object beside scalars or admit tuples and objects. | Names, kinds, the parameters' mapping, validation and formatting are concrete. A kind is an `IntEnum` member, which cannot become an `Any` value, so `replace()` constructs by class name instead of `type(self)`. The opt-in puts `enum`, `keyword` and `types` in the tracked import closure, and a non-opt-in caller that makes a `Parameter` restarts compilation with full identity tracking; `re` is kept out of the closure, at the cost of an ASCII-only name test until `str.isidentifier()` is supported. |
| `threading` | contract: a caller keeps timers of different functions in one list and reads their arguments back ([test](../tests/programs/library/lib_threading_boundary.py)) | `Thread` and `Timer` keep a target or function with its argument tuple and keyword dict, and `Condition` its lock, of whatever supported types each caller gives, as attributes that callers read back (`Timer.function`, `args`, `kwargs`), while every thread and every timer is an object of one class, so that `_active`, `_limbo`, `enumerate()` and a caller's list hold them together. | A typed port has two forms, and each rejects programs that compile today: one `Thread` class for every target keeps the call in a closure and cannot give those attributes back, and a `Timer` class template keeps them but makes timers of two functions two classes, which one list does not hold. Class templates under ordinary classes now compile ([#962](https://github.com/den-run-ai/pystachy/issues/962)); both still wait on `id()` of an object and a function's `__name__` through `getattr()` and `hasattr()`. Names after conversion, counters, waiters and normalized lock state can be concrete. Preserve existing constructor errors; this inventory adds no thread execution support. |

`pathlib` no longer opts in. Its constructor's parameters are still `Any`, which each call now
infers: the constructor's code is compiled for a call's argument types, while every field has
an annotated type, so a path has one class whatever made it
([fixed-layout constructors](language/typing.md#class-templates-and-generic-classes)). An argument that is
neither a path nor a `str` still raises `TypeError` when the call runs, and subclasses of the
path classes compile as before
([test](../tests/programs/library/lib_pathlib_subclass.py)). The comment had put `pathlib`
and the modules it imports in the closure that tracks numeric identity, in every program that
imports it. On [#1632](https://github.com/den-run-ai/pystachy/pull/1632),
`tests/programs/library/lib_pathlib.py` compiled to 64,093 lines of LLVM IR
instead of 83,331, with no `pys_dyn_*` call site instead of 1,553 (960 of them integer
boxes). The AOT executable shrank from 776,096 to 589,936 bytes. Both IR counts
precede runtime linking. Restoring the comment reproduced the larger measurements.

## JSON repair port modules

All paths below are relative to `ports/json_repair/`. Parsed JSON data has a
closed mathematical value set; the current mutable output API and its callers
can have a broader storage contract. Prefer a typed implementation for a closed
consumer only after preserving its aliases and the boundary to existing users.

| Modules | Status | Current boundary | Concrete work and remaining containment debt |
|---|---|---|---|
| `json_repair.py`, `json_parser.py` | contract: callers change a repaired document through `Any` ([test](../tests/programs/apps/port_json_repair.py)) | Dynamic repaired results, nested mutable containers, optional result/log tuples and interoperability with dynamic JSON. | Scanning state is largely concrete already. Recursive typed storage needs two things a closed union lacks: a promoting integer member, since a repaired document keeps integers past 64 bits ([test](../tests/programs/apps/port_json_repair_wide.py), [#907](https://github.com/den-run-ai/pystachy/issues/907)), and a result that is a value, a `(value, log)` tuple or a `str` by `repair_json()`'s arguments. Returning logs through an existing `Any` tuple is an alias/layout boundary to preserve. |

Fifteen modules of the port no longer opt in. Eleven only pass values on: the three
package `__init__.py` files, `parse_comment.py`, `parse_number.py`,
`parser_parenthesized.py`, `utils/json_context.py`, `utils/object_comparer.py` and, under
`parse_string_helpers/`, `parse_json_llm_block.py`, `parse_boolean_or_null.py` and
`object_value_context.py`. Their `Any` annotations are inferred from each call, and the two
modules above box what they store. Removing these comments is containment, not a cost
result. The modules stay inside the import closure that tracks numeric identity, so the initial
[eleven removals](https://github.com/den-run-ai/pystachy/blob/b3a4d56981125d2da95ac920c7baedaafe5a9898/docs/dynamic-any-boundaries.md#json-repair-port-modules) reduced
`tests/programs/apps/port_json_repair.py` from 40,361 to 40,175 lines of LLVM IR, with
the same 403 numeric box sites.

The twelfth, `__main__.py`, only serializes the repair result: `json.dumps()` of a value
that is already `Any`'s selects the dynamic encoder from the argument's type in any module
(`tests/programs/inference/dynany_dumps_caller.py`). Its comment was what put `argparse`
and the modules it imports in the tracked closure. With the
[compiler used for the measurement](https://github.com/den-run-ai/pystachy/tree/b3a4d56981125d2da95ac920c7baedaafe5a9898),
`tests/programs/apps/port_json_repair_cli.py` compiled to
121,437 lines of LLVM IR instead of 143,887, with 403 numeric box sites instead of 1,696
and 592 `pys_dyn_*` call sites instead of 2,596. The AOT executable shrank from 1,085,032
to 949,432 bytes. Both IR counts precede runtime linking. Restoring the comment
reproduced the larger measurements. The parser still tracks
identity, so the repair itself is the same code: the result is compilation work and size,
not steady-state speed or allocation.

The array and object scanners fill fresh `list[Any]` and `dict[str, Any]` containers
created by the parser. Both store boxed values and preserve mutable aliases. The
object scanner classifies an empty object before reparsing it. An escaped key can
produce a replacement dictionary, and malformed object syntax can produce a list.
Each path returns the reparsed value directly. In the string scanner,
`_prepare_string_entry()` uses a `StringParseState | None` local for the first slot of
its result. Both early and continuing returns then have the same pair layout. The
second slot may still carry a dynamic value supplied by the parser. All three scanners
remain in the parser's identity-tracking import closure.

## What removing each comment meets

When `pathlib`'s comment was removed, each remaining comment was also removed alone and the
programs that import its module were run (JIT). The first diagnostic names the contract the
module still needs, which its row above describes. The `logging` and `threading` rows were
measured again once subclasses of class templates, also those whose own `__init__` is a template,
template-typed fields of declaration-time specializations and class templates under ordinary
classes were supported (#962);
`threading`'s programs are those that import it, `logging`, `subprocess` or
`concurrent.futures`.

| Module | Programs failing | First diagnostic |
|---|---|---|
| `tomllib._re` | 1 of 8 | `comparing closed union values requires narrowing`: a consumer tests `is` on the `int \| float` result, and only tracked identity answers that for two numbers |
| `tomllib._types` | 7 of 8 | `make_safe_parse_float() returns both` `float` and its wrapper function |
| `tomllib._parser` | 7 of 8 | `NestedDict`: `typing.Any is only supported in the parameter and return annotations` (its field holds any parsed value) |
| `logging` | 5 of 5 | `_make_style() returns both StrFormatStyle[str, None] and StringTemplateStyle[str, None, Template]`: the styles' objects begin as two specializations of `PercentStyle`, which one result cannot hold (`Logger`, a class template under the ordinary class `Filterer`, is inside the [template hierarchy subset](language/typing.md#class-templates-under-an-ordinary-class)) |
| `_pystachy_percent` | 5 of 30 | `_Formatter`: `typing.Any is only supported in the parameter and return annotations` (its fields hold the argument pack) |
| `inspect` | 12 of 12 | `cannot infer the type of '_VOID_PARAMETERS'`: a list of `Parameter` objects, whose default and annotation type the class |
| `threading` | 7 of 26 | `Condition`: `typing.Any is only supported in the parameter and return annotations`, its field that holds the supplied lock, where `Semaphore`'s `_cond` is made; without it, `cannot infer the type of '_active'`: `dict[int, "Thread"]` names a class template, and one registry cannot hold threads of two specializations |
| `json_repair.py` | 15 of 18 | `repair_json() returns both` a `(value, log)` tuple and a value |
| `json_parser.py` | 18 of 18 | `JSONParser`: `typing.Any is only supported in the parameter and return annotations` |

`_pystachy_json_any` is the dynamic JSON codec itself: no program reaches it without an
opt-in somewhere.

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
fallback. Those need a separate proof before the corresponding bookkeeping can
be removed. Preserve existing ordinary-mode IR/diagnostics and library consumers
throughout that work; do not claim that all remaining opt-ins are unavoidable.
