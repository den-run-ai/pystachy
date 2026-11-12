# Blocker chain for `import mypyc.ir.ops` (12 November 2026)

Research evidence, not for `main`. Compiler: a local merge of #1274 (`bea7ce23`), #1275
(`4c59ec47`), #1276 (`be679fa1`) and #1277 (`4973a11a`) on `a339ab3`. Input: unmodified mypy
2.4.1 sources, except the probe patches in [probe-patches.diff](probe-patches.diff), with the
throwing stand-ins in [../../stand-ins](../../stand-ins) (`librt`, `ast_serialize`) and
[../../stand-ins/stdlib](../../stand-ins/stdlib) (`pprint`, `hashlib`, `platform`, `gc`,
`importlib.resources`, `importlib.machinery`, `importlib.util`, `sysconfig`). Each step patches
the first error on a scratch copy to reach the next; a patch is a probe, not a proposed change.

## Why this module

mypyc's IR (`mypyc.ir.ops`, `mypyc.ir.rtypes`) eagerly imports 6 project modules: `mypy.util`,
`mypyc.common`, `mypyc.ir.deps`, `mypyc.ir.ops`, `mypyc.ir.rtypes` and `mypyc.namegen`. The
`mypy.nodes` closure has 10, `mypy.types` 16 and `mypyc.irbuild.builder` 146. Today 13 of
mypyc's 102 modules compile (package `__init__`s and leaves such as `mypyc.namegen`, whose 5
upstream unit tests already run natively: `tests/upstream/pytest`).

## Chain

| Step | First error | Gap | Probe patch |
|---|---|---|---|
| 1 | `ops.py:1461` `op_str: Final = {ADD: "+", ...}` | Untyped `Final` display in a class body (fixed by #1280); its keys also name earlier class attributes, which class-body values cannot read yet | `Final[dict[int, str]]` |
| 2 | `util.py:374` `fields_cache: Final[dict[type[object], list[str]]]` | Class objects as values (#805); the module-level global is compiled although mypyc never calls `get_class_descriptors` | raising `get_class_descriptors`/`replace_object_state` |
| 3 | `deps.py:115` `self.include_dirs: Final = include_dirs or []` | Field inference of `x or []` | `Final[list[str]]` |
| 4 | `rtypes.py:217` `dependencies: tuple[Dependency, ...] \| None` | Runtime-length tuples of objects; `Dependency` is a union of three unrelated classes | `list[Dependency]` |
| 5 | `rtypes.py:236` `primitive_map: ClassVar[dict[str, RPrimitive]] = {}` | `ClassVar` (stacked follow-up of #1280) | plain annotation |
| 6 | `rtypes.py:263` `self._may_be_immortal = may_be_immortal and HAVE_IMMORTAL` | Field inference of `and` with an imported `Final` global | `: bool` |
| 7 | `rtypes.py:548` `[("...", ()), ("...", (LIBRT_STRINGS,))]` | A list of tuples whose items differ in length (`tuple[Capsule, ...]`) | named `list[Dependency]` values |
| 8 | `rtypes.py:843` `self.types = tuple(types)` | Runtime-length tuple of `RType` objects | `list[RType]` |
| 9 | `rtypes.py:843` `self.unique_id = self.accept(TupleNameVisitor())` | Generic visitor: `accept(self, visitor: RTypeVisitor[T]) -> T` over `class RTypeVisitor(Generic[T])` subclasses | stop |

Step 9 is the proposal's "virtual generic method" and #962 (generic class as a base). It also
gates mypy's `NodeVisitor[T]`, `TypeVisitor[T]` and mypyc's `OpVisitor[T]`, so it is the next
structural item for both programs; steps 1 to 8 are small typing and inference forms, except
runtime-length object tuples (4, 7, 8) and class objects (2).
