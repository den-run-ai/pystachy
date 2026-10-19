# `_ast`: typed expression-node prototype

This is a small native `_ast` constructor surface, related to [#491](https://github.com/den-run-ai/pystachy/issues/491)
and [#11](https://github.com/den-run-ai/pystachy/issues/11). It is experimental.
`import _ast` loads `lib/_pystachy_ast.py` through the existing builtin stand-in
table. Under CPython, the same import loads CPython's actual builtin module.
No CPython embedding, foreign object handles or new runtime ABI are involved.

The useful operation established here is constructing, inspecting and rewriting
typed expression trees. The differential consumer recursively folds a ten-node
arithmetic tree to five nodes and evaluates both trees for four variable values,
while leaving the input tree intact. This is not a source parser or a claim that
CPython's `ast.py`, `inspect`, `unittest`, pytest or regrtest now work.

## Supported surface

| Surface | Contract |
|---|---|
| Bases | `AST`, `mod`, `expr`, `expr_context`, `boolop`, `operator`, `unaryop`, `cmpop`; normal subclass `isinstance` checks |
| Roots | `Expression(body: expr)` |
| Leaves | `Constant(value, kind=None)` for `int`, `float`, `str`, `bool`, `None`; `Name(id: str, ctx: expr_context | None = Load())` |
| Operations | `BinOp(left, op: operator, right)`, `UnaryOp(op: unaryop, operand)`, `BoolOp(op: boolop, values: list[expr])`, `Compare(left, ops: list[cmpop], comparators: list[expr])`, `IfExp(test, body, orelse)`, `NamedExpr(target, value)` |
| Calls and access | `Call(func, args: list[expr], keywords: list[keyword])`, `keyword(arg: str | None, value)`, `Attribute(value, attr: str, ctx)`, `Subscript(value, slice, ctx)`, `Slice(lower=None, upper=None, step=None)`, `Starred(value, ctx)` |
| Displays | `List(elts, ctx)`, `Tuple(elts, ctx)`, `Set(elts)`, `Dict(keys: list[expr | None], values: list[expr])`; a `None` key stands for `**mapping` |
| Generators and coroutines | `Await(value)`, `Yield(value=None)`, `YieldFrom(value)` |
| Context tags | `Load`, `Store`, `Del` |
| Boolean operator tags | `And`, `Or` |
| Binary operator tags | `Add`, `Sub`, `Mult`, `MatMult`, `Div`, `Mod`, `Pow`, `LShift`, `RShift`, `BitOr`, `BitXor`, `BitAnd`, `FloorDiv` |
| Unary operator tags | `Invert`, `Not`, `UAdd`, `USub` |
| Comparison tags | `Eq`, `NotEq`, `Lt`, `LtE`, `Gt`, `GtE`, `Is`, `IsNot`, `In`, `NotIn` |
| Metadata | CPython 3.13's `_fields`, `_attributes` and `__match_args__` tuples for these classes and instances, including inherited metadata; `type(node).__module__` and reprs name `ast`, as CPython's types do |
| Flags | `PyCF_ONLY_AST`, `PyCF_TYPE_COMMENTS`, `PyCF_ALLOW_TOP_LEVEL_AWAIT`, `PyCF_OPTIMIZED_AST`; exposing values does not implement the associated `compile()` operations |
| Mutation | Existing typed fields can be reassigned; sharing a child preserves reference identity and makes mutations visible through its parents |

Constructors accept the named fields as positional or keyword arguments. Supply
all required fields explicitly. Unannotated fields above are `expr`. As in CPython
3.13, an optional field left out is `None`, a list field left out is a new empty
list of the node's own, and a context left out is the one `Load` object that every
node shares (`List().ctx is Name("x").ctx`). Explicit `ctx=None` stays `None`, and
an explicitly supplied context or list retains its identity: the node keeps the
list it is given, not a copy. Changing one name's `ctx` field does not change
another name's field. Operator tags describe syntax; their presence does not add
evaluation of those operators to the module.

Example, unchanged under CPython:

```python
import _ast as ast

node = ast.BinOp(ast.Constant(2), ast.Add(), ast.Constant(3))
print(node._fields)                       # ('left', 'op', 'right')
print(isinstance(node.left, ast.Constant)) # True
node.right = ast.Constant(5)
```

## Explicit boundaries

- No statements, modules of statements, comprehensions (`ListComp` and the
  others, `comprehension`), `Lambda` and its `arguments`/`arg`, f-string nodes
  (`JoinedStr`, `FormattedValue`), function definitions, pattern matching or type
  parameters. Importing an absent class such as `Module` is rejected by the compiler.
- `keyword` takes `arg` explicitly (`keyword(None, value)` for `**mapping`): CPython
  3.13's default `None` precedes the required `value`, which a typed constructor
  cannot express. A list field takes a list; CPython keeps an explicit `None` there
  and rejects it only in `compile()`.
- No source parser or `compile(..., PyCF_ONLY_AST)` bridge. `compile()` remains
  an unsupported call. `_ast` itself does not have CPython's `ast.parse()` helper;
  adding an inert function with that name would not implement the public API.
- No source-location fields. `_attributes` accurately describes the CPython
  schema but those locations are not allocated on prototype instances.
  `Constant(1, lineno=1)` is explicitly rejected rather than returning invented
  coordinates. No `fix_missing_locations`, `get_source_segment` or location-based
  tools are promised.
- No bytes, complex, ellipsis, tuple or frozenset constant values. In particular,
  the current compiler cannot place `bytes` in a closed union; widening
  `Constant.value` to include it is not just a constructor change.
- No `_field_types`, arbitrary keyword fields, missing-required-field nodes,
  class monkey-patching, pickling, visitor dispatch by runtime attribute names,
  or full dynamic reflection. `__module__` and other general class reflection
  follow ordinary Pystachy classes, not CPython's generated AST class machinery.
  `_field_types` needs actual class/type objects and optional unions; a mapping
  of field names to strings would not implement that API and is not substituted.
- `__match_args__` exposes the correct positional field order, but the compiler
  still rejects all `match` statements, including class patterns on these nodes.
  The tests exercise metadata through base-typed objects and inherited classes,
  and separately assert a clear diagnostic for a nested AST class pattern.
- Typed constructors and mutation enforce the field types they declare. CPython
  permits several malformed tree constructions and validates them later in
  `compile()`. This slice does not implement that delayed validation protocol.
- Traversal, transformation, printing and evaluation in the tests are application
  functions, not an implementation of `ast.walk`, `NodeVisitor`, `NodeTransformer`,
  `ast.dump`, `ast.unparse` or `ast.literal_eval`.

The public `AST` hierarchy makes typed visitors feasible, but deep recursion,
cycles and whole-schema compatibility have not been established. A future parser
must impose suitable resource limits and preserve CPython's error semantics.

## Why not return the compiler's own nodes?

`src/pystachy_compiler/syntax.py` stores the compiler's `Node` as `kind`, `s`,
`line` and `kids`, plus compiler-specific fields. It is not CPython's AST schema:
it loses column/end spans, normalizes some syntax and does not provide the public
node-class hierarchy. `diagnostics.fail()` prints an error and calls `sys.exit(1)`;
reusing the current parser as `ast.parse()` would unexpectedly terminate a consumer
instead of raising a catchable `SyntaxError`. Returning those nodes or swallowing
the error would hide these gaps.

A follow-up should introduce structured parser errors and retain source spans,
then map a measured syntax subset to public nodes. It needs parser-to-object and
object-to-compiler validation tests before exposing `compile(AST, ...)`. This PR
does not change the parser or imply that arbitrary runtime code generation fits
Pystachy's AOT model.

## PyPy and GraalPy comparison

- [PyPy's parser architecture](https://doc.pypy.org/parser.html#building-ast)
  generates the public AST bindings and internal compiler classes from ASDL,
  then explicitly builds those trees from its parser. At PyPy revision
  `3ce8ee955977343ff96902fdedbc5dad535d0f95`, the `_ast` module exports the
  generated `AST_TYPES`; the schema and parser/compile integration are separate
  pieces. This supports a small explicit schema slice here, without copying
  RPython's interpreter/object-space implementation.
- GraalPy revision `7e7182b1036d56f8e89ecc9c7a86cee292180aa6` similarly uses
  `AstState`/`AstTypeFactory` to construct public classes and explicit
  `Sst2ObjVisitor`, `Obj2Sst` and validator stages to bridge the parser. Merely
  declaring its class names would omit the actual compatibility machinery.
  See its [AST module implementation](https://github.com/oracle/graalpython/blob/7e7182b1036d56f8e89ecc9c7a86cee292180aa6/graalpython/com.oracle.graal.python/src/com/oracle/graal/python/builtins/modules/ast/AstModuleBuiltins.java).
- The supported fields and flags follow [CPython 3.13's AST reference](https://docs.python.org/3.13/library/ast.html),
  with CPython **3.13.16** as the executable differential oracle. This is a new
  typed implementation of the interface; no PyPy/GraalPy implementation code is
  copied or vendored.

## Regression found while prototyping

Ordinary class reads of `_fields` and `_field_defaults` incorrectly used the
compiler's NamedTuple path. For example, `AST._fields` returned internal class
field names instead of `()`. The two special cases now require an actual
NamedTuple class. `tests/class_field_metadata.py` checks ordinary class and
inherited class reads, instance reads and shared-dictionary mutation. NamedTuple
regressions remain part of the focused verification. Inheritance from either
`typing.NamedTuple` or a `collections.namedtuple()` class remains unsupported;
the two `tests/errors/namedtuple_subclass_*.py` regressions explicitly reject
subclasses that would read `_fields` or `_field_defaults`, instead of allowing
the metadata path to crash or silently treating them as ordinary classes.

## Reproduce

```sh
make
PYTHON=python3.13 tests/record.sh lib_ast_nodes lib_ast_transform lib_ast_match_args \
  lib_ast_name_default lib_ast_expressions class_field_metadata
tests/run.sh ./pystachy "jit aot" tests/lib_ast_*.py \
  tests/class_field_metadata.py tests/errors/lib_ast_*.py \
  tests/errors/namedtuple_subclass_*.py
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy "jit aot" \
  tests/lib_ast_*.py
```

The tests compare the same programs directly to CPython's native `_ast`, including
all supported constant kinds and operator tags, inherited metadata, field
mutation, shared children, recursive construction and a tree-transform consumer.
`tests/lib_ast_expressions.py` adds every other node's metadata, the 3.13
defaults (fresh lists, the shared `Load`, `None`), kept lists, and a source
printer and evaluator over boolean operations, chained comparisons, calls with
keywords and unpacking, subscripts, slices and displays, then rewrites shared
children in place. Rejection tests cover bytes constants, location keywords,
statement and comprehension nodes, a `keyword` without `arg`, a `None` list field,
invalid operator types, the unsupported `compile` bridge, actual `match`
statements and NamedTuple subclass metadata. These measure API
execution and honest boundaries; they do not turn an import-only audit result
into a claim of upstream test-suite compatibility.
