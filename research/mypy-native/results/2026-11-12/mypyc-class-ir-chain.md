# Blocker chain for `import mypyc.ir.class_ir` (12 November 2026, later)

Research evidence, not for `main`. Compiler: the hosted compiler of a local merge of `main`
(`8434a911`) with every open PR of this work (#1275 to #1282, #1286, #1292 to #1298 and #1317,
at their heads of 12 November 05:50 UTC; integration commit `e8cb861a`). Input: mypy 2.4.1
sources with the earlier [probe patches](probe-patches.diff) (only `util.py:374` still matters)
and the throwing stand-ins of [../../stand-ins](../../stand-ins), now also `inspect`.

```sh
PYSTACHY_PATH="$PKGS:stand-ins/stdlib:stand-ins" python3.13 pystachy.py ir p.py -o /dev/null
```

| Probe | First error | Gap | Next step |
|---|---|---|---|
| `import mypyc.ir.rtypes` | `rtypes.py:759`: `'ClassIR' is imported only under if TYPE_CHECKING:, from module 'mypyc.ir.class_ir', which the program does not import` | The boundary of #1317: CPython never evaluates the annotation, but Pystachy needs the class, and nothing loads `class_ir` | Probe a module that imports `class_ir` |
| `import mypyc.ir.class_ir` | `func_ir.py:5` `import inspect` | `func_ir` builds `_ARG_KIND_TO_INSPECT` from `inspect.Parameter`'s kinds as it initializes; `get_text_signature` builds `Parameter` and `Signature` objects | Stand-in `stand-ins/stdlib/inspect.py` (kinds only; building raises) |
| same | `errorcodes.py:14` `sub_code_map: dict[str, set[str]] = defaultdict(set)` | `lib/collections`' `defaultdict` is a generic class around a `dict`, not a `dict`: a `dict[K, V]` annotation can hold neither it nor bind its type variables (`defaultdict[str, set[str]]` works) | Probe patch: annotate `defaultdict[str, set[str]]` |
| same | `visitor.py:363` `class NodeVisitor(Generic[T], ExpressionVisitor[T], StatementVisitor[T], PatternVisitor[T])` | Several generic, method-only bases (mypyc traits). Pystachy takes one primary base and one method-only secondary base (`program.py` `subclass_problem`), neither generic | Stop: the next structural item |

`NodeVisitor` re-declares all 81 methods of its three bases (and 4 more), each raising
`NotImplementedError`; nodes take the bases as parameter types
(`def accept(self, visitor: ExpressionVisitor[T]) -> T`), and checkers derive from one of them
plus another base (`ExpressionChecker(ExpressionVisitor[Type], ExpressionCheckerSharedApi)`).
The same shape gates `TypeVisitor[T]` (`mypy/type_visitor.py`) and mypyc's `OpVisitor[T]`.

## With the generic traits (#1335)

Merged into the integration tree (`ff20bca1`), #1335 takes the chain past `NodeVisitor`:

| Probe | First error | Gap |
|---|---|---|
| `import mypyc.ir.class_ir` | `modules_state.py:20` `self.node_fixer: NodeFixer \| None` | #1317's boundary: `NodeFixer` is imported only under `if TYPE_CHECKING:` from `mypy.fixup`, which this program never imports (a real mypyc run does) |
| `import mypy.fixup` then `import mypyc.ir.class_ir` | `bogus_type.py:17` `from mypy_extensions import FlexibleAlias` | `FlexibleAlias` (also the first blocker of 86 modules in the import sweep) |

`FlexibleAlias` needs three things, in this order of risk:

1. `MYPYC = False` / `if MYPYC:` decided at compile time. Only `TYPE_CHECKING = False` is today;
   deciding every module-level boolean flag would reject programs that assign one from another
   module. A sound narrow rule: an `if NAME:` that the statement right before it binds to a bool
   literal, as nothing can run between them.
2. `Bogus = FlexibleAlias[T, X]` as a generic type alias whose value is `X` (mypy's meaning;
   CPython never evaluates the postponed annotations).
3. Sentinel defaults, which mypy's `Bogus` exists for: `values: Bogus[list[Type]] = _dummy`
   with `_dummy: Final[Any] = object()`, read as `self.values if values is _dummy else values`
   (about 90 uses in `mypy/types.py`). Pystachy cannot type the default (`expected list[int],
   got object`), nor a union of a container and a class. A design that keeps CPython's
   semantics: pass a static "unset" pointer for an omitted pointer-typed argument (or the
   sentinel name itself), compile `p is _dummy` as a test of it, and accept reads of `p` only
   where such a test excludes the sentinel (otherwise a compile-time error); scalar parameters
   keep int sentinels (`_dummy_int`).
