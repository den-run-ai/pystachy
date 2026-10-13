# Applies the parsy 2.2 -> Pystachy port edits to the verbatim source, counting them
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src).read()
edits = []
def edit(why, old, new, n=1):
    global s
    c = s.count(old)
    assert c == n, (why, old, c)
    s = s.replace(old, new)
    edits.append((why, n))
edit("enum: not a module Pystachy has", "import enum\n", "")
edit("functools.wraps: for generate(), generators are removed on purpose", "from functools import wraps\n", "")
edit("functools.wraps", "    @wraps(fn)\n", "")
i = s.index("def from_enum(")
j = s.index("class forward_declaration(")
s = s[:i] + s[j:]
edits.append(("from_enum: enum", 1))
edit("streams are str: bytes are removed on purpose, a list stream needs its item type", "str | bytes | list", "str", 19)
edit("max is float('inf') too", "max: int = None", "max: int | float | None = None")
edit("max is float('inf') too", 'max: int = float("inf")', 'max: int | float = float("inf")', 2)
edit("Any: a template parameter", '''@dataclass
class Result:
    status: bool
    index: int
    value: Any
    furthest: int
    expected: FrozenSet[str]
''', '''class Result:  # pystachy: value has no annotation (Any): a class template
    def __init__(self, status: bool, index: int, value, furthest: int, expected: FrozenSet[str]):
        self.status = status
        self.index = index
        self.value = value
        self.furthest = furthest
        self.expected = expected
''')
edit("Any", " -> Any:", ":", 2)
edit("Any", " -> tuple[Any, str]:", ":")
edit("Any", "bind_fn: Callable[[Any], Parser]", "bind_fn")
edit("bare Callable", "map_function: Callable)", "map_function)")
edit("bare Callable", "combine_fn: Callable)", "combine_fn)", 2)
edit("Any", "value: Any)", "value)", 2)
edit("Any", "default: Any = None", "default=None")
edit("Any", "item: Any,", "item,")
edit("Callable[..., bool]", "Callable[..., bool]", "Callable[[str], bool]", 2)
for a in sys.argv[3:]:
    exec(open(a).read())
open(dst, "w").write(s)
print(sum(n for _, n in edits), "replacements in", len(edits), "edits", file=sys.stderr)
