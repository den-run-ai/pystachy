# blocker log for import mypy.nodes (patched copy)
- nodes.py:3863 class attr 'FLAGS: Final = [...]' (untyped Final, list value) -> annotated Final[list[str]]
- nodes.py:444 MypyFile "inheritance with generic class templates": init_template() sees
  `self.alias_deps = defaultdict(set)` in __init__ (makes_tmpl: a call of class template
  collections$defaultdict), although the class declares `alias_deps: defaultdict[str, set[str]]`.
  Candidate fix: ignore template calls stored into fields whose class annotation is a complete type.

## Library blockers after mypy_extensions (#1275) and librt (#1276), in sweep order
pprint (options.py: pformat in __repr__) -> platform (defaults.py: machine()) -> importlib.resources
(util.py: TYPESHED_DIR) -> mypy_extensions.FlexibleAlias (bogus_type.py, 80 modules) -> gc as a
compiler-known module (build.py) -> contextlib.ExitStack (checker.py) -> inspect, ast, subprocess
(tools, stubgen, main).

## Language blockers seen with probe stubs
- untyped `Final` class attribute with a dict/set/tuple/list display (nodes.py:3863; 14 modules)
- `defaultdict(...)` stored where `dict[K, V]` is declared (errorcodes.py:14): lib defaultdict is a
  wrapper class, not a dict subtype
- module-level `orjson: Any` before an optional import (util.py:19)
- class NodeVisitor(Generic[T], ExpressionVisitor[T], ...): generic class with other bases (#962)
- graph_utils.topsort(Iterator[...]) generator class base; ModulesState annotation
- errorcodes.py:14 'sub_code_map: dict[str, set[str]] = defaultdict(set)' (defaultdict stored as dict) -> annotated defaultdict[str, set[str]] (patch)
- util.py:19 'orjson: Any' declaration before an optional import (Any outside parameters) -> removed (patch)
- util.py:374 'fields_cache: Final[dict[type[object], list[str]]]' and get_class_descriptors(cls: type[object]) with inspect: class objects as values (#805) -> stop
