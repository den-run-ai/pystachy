# A field that __init__ stores from a or b, or a and b, takes the type both operands have, or
# for a or b, a's without None where b has it or is an empty list or dict display (mypyc's
# SourceDep: self.include_dirs = include_dirs or []).
class SourceDep:
    def __init__(
        self,
        path: str,
        include_dirs: list[str] | None = None,
        name: str | None = None,
        count: int | None = None,
        options: dict[str, int] | None = None,
        internal: bool = True,
        shared: bool = False,
    ) -> None:
        self.path = path
        self.include_dirs = include_dirs or []
        self.name = name or path
        self.count = count or 0
        self.options = options or {}
        self.both = internal and shared
        self.either = internal or shared


a = SourceDep("bytes_ops.c")
b = SourceDep("vecs.c", ["vecs"], "v", 3, {"x": 1}, False, True)
a.include_dirs.append("lib")
print(a.include_dirs, a.name, a.count, a.options, a.both, a.either)
print(b.include_dirs, b.name, b.count, b.options, b.both, b.either)
