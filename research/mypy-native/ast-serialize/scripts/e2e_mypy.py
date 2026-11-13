"""End to end under CPython: mypy.nativeparse's reader on the port's bytes and on the extension's
gives the same mypy tree (str(MypyFile), mypy's StrConv dump), errors and imports."""
import importlib.util
import os
import sys
from pathlib import Path

import ast_serialize as rust
from mypy.errors import Errors
from mypy.nodes import FileRawData
from mypy.options import Options
from mypy.parse import load_from_raw

sys.setrecursionlimit(20000)
LIB = Path(sys.argv[1])
init = LIB / "ast_serialize" / "__init__.py"
spec = importlib.util.spec_from_file_location("pystachy_ast_serialize", init,
                                              submodule_search_locations=[str(init.parent)])
port = importlib.util.module_from_spec(spec)
sys.modules["pystachy_ast_serialize"] = port
spec.loader.exec_module(port)


def tree_of(mod, path, options, skip):
    b, errors, ignores, import_bytes, data = mod.parse(
        str(path), None, skip_function_bodies=skip, python_version=options.python_version,
        platform=options.platform, always_true=options.always_true,
        always_false=options.always_false, cache_version=5)
    raw = FileRawData(b, import_bytes, errors, dict(ignores), data["is_partial_package"],
                      data["uses_template_strings"], data["source_hash"], data["mypy_comments"])
    errs = Errors(options)
    tree = load_from_raw(str(path), "m", raw, errs, options)
    return str(tree), [str(i) for i in tree.imports], errs.new_messages() if hasattr(errs, "new_messages") else []


def files(paths):
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for root, dirs, fs in os.walk(p):
                dirs.sort()
                for f in sorted(fs):
                    if f.endswith((".py", ".pyi")):
                        yield Path(root) / f
        else:
            yield p


options = Options()
options.python_version = (3, 13)
same = total = failed = 0
for path in files(sys.argv[2:]):
    for skip in (False, True):
        total += 1
        try:
            a = tree_of(rust, path, options, skip)
        except Exception as e:
            a = ("extension or reader failed", type(e).__name__, str(e))
            failed += 1
        try:
            b = tree_of(port, path, options, skip)
        except Exception as e:
            b = ("port or reader failed", type(e).__name__, str(e))
        if a == b:
            same += 1
        else:
            print("DIFFERENT", path, skip)
print(f"mypy trees: {same}/{total} identical ({failed} where the extension's bytes did not load)")
