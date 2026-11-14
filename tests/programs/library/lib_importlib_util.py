# importlib.util.resolve_name(): a relative module name against its package, with CPython's
# errors for a relative name without a package and for one that leaves the top-level package.
import importlib.util
from importlib.util import resolve_name

print(resolve_name("bacon", None), resolve_name("bacon", "spam"), resolve_name("a.b", ""))
print(resolve_name(".bacon", "spam.eggs"), resolve_name("..bacon", "spam.eggs"))
print(resolve_name(".", "spam.eggs"), resolve_name("..", "spam.eggs"), resolve_name("...a.b", "x.y.z"))

# mypyc's use (mypyc/irbuild/statement.py): the module a from-import names, by its level
for relative, name, package in [(0, "os.path", "mypy"), (1, "types", "mypy"), (2, "common", "mypyc.irbuild"), (1, "", "mypy.server")]:
    print(importlib.util.resolve_name("." * relative + name, package))

cases: list[tuple[str, str | None]] = [(".bacon", ""), (".bacon", None), ("..bacon", "spam"), ("....a", "x.y.z"), ("..", "top")]
for target, anchor in cases:
    try:
        print(resolve_name(target, anchor))
    except ImportError as e:
        print(type(e).__name__, e)
