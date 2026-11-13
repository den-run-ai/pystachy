"""Check lib/ast_serialize/ on CPython against ast_serialize 0.13.1's Rust extension.

This checks the port's source, not compiled Pystachy (tests/programs/library/lib_ast_serialize_*.py
compare that): for every Python file under the given directories (or the given files), parse()
of the port must return what the extension returns, all five elements (the AST bytes, the
syntax errors, the type ignores, the imports metadata and the dict of extra data), for each
option set. Files the extension reports syntax errors for are compared too but counted apart.
With --type-strings, parse_type_string() is compared on the string annotations and type comments
of the files and on hand-written cases. A mismatch reports the file and the first differing
offset of the bytes, decoded into the tags and values around it.
Needs ast-serialize==0.13.1 (mypy's native parser; tools/requirements-dev.txt).
Usage: python3 -I tools/ast_serialize_check.py [--options default,skip,...] [--type-strings]
       [--source none|str|bytes] [--limit N] [--quiet] PATH...
"""
import argparse
import importlib.metadata
import importlib.util
import os
from pathlib import Path
import struct
import sys
import time

import ast_serialize as rust

LIB = Path(__file__).resolve().parent.parent / "lib"
sys.dont_write_bytecode = True  # (no __pycache__ in lib/)
sys.setrecursionlimit(20000)

OPTION_SETS = {
    "default": {"python_version": (3, 13), "platform": "linux"},
    "skip": {"python_version": (3, 13), "platform": "linux", "skip_function_bodies": True},
    "cv5": {"python_version": (3, 13), "platform": "linux", "cache_version": 5},
    "cv7": {"python_version": (3, 13), "platform": "linux", "cache_version": 7},
    "py38-win": {"python_version": (3, 8), "platform": "win32", "cache_version": 5},
    "py314-darwin": {"python_version": (3, 14), "platform": "darwin", "cache_version": 5,
                     "skip_function_bodies": True},
    "always": {"python_version": (3, 11), "platform": "linux", "cache_version": 5,
               "always_true": ["DEBUG", "True", "TYPE_CHECKING"], "always_false": ["PY3", "False", "MYPY"]},
}


def load():
    init = LIB / "ast_serialize" / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "pystachy_ast_serialize", init, submodule_search_locations=[str(init.parent)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["pystachy_ast_serialize"] = module
    spec.loader.exec_module(module)
    return module


TAGS = {
    0: "False", 1: "True", 2: "None", 53: "Decorator", 60: "ClassDef", 255: "END",
    104: "UnboundType", 105: "UnpackType", 112: "TupleType", 113: "TypedDictType", 115: "UnionType",
    118: "TypeList", 119: "EllipsisType", 120: "RawExpressionType", 121: "CallType",
    160: "ExprStmt", 161: "Call", 162: "Name", 163: "Str", 164: "Import", 165: "Member", 166: "Op",
    167: "Int", 168: "If", 169: "Assign", 170: "Tuple", 171: "Block", 172: "Index", 173: "List",
    174: "Set", 175: "Return", 176: "While", 177: "Comparison", 178: "BoolOp", 179: "FuncDef",
    180: "Pass", 181: "Float", 182: "Unary", 183: "Dict", 184: "Complex", 185: "Slice",
    186: "TempNode", 187: "Raise", 188: "Break", 189: "Continue", 190: "Generator", 191: "Yield",
    192: "YieldFrom", 193: "ListComp", 194: "SetComp", 195: "DictComp", 196: "ImportFrom",
    197: "Assert", 198: "For", 199: "With", 200: "OpAssign", 201: "Try", 202: "Ellipsis",
    203: "Conditional", 204: "Del", 205: "FString", 206: "FStringInterp", 207: "Lambda",
    208: "Walrus", 209: "Star", 210: "Bytes", 211: "Global", 212: "Nonlocal", 213: "Await",
    214: "BigInt", 215: "ImportAll", 216: "Match", 217: "AsPattern", 218: "OrPattern",
    219: "ValuePattern", 220: "SingletonPattern", 221: "SequencePattern", 222: "StarredPattern",
    223: "MappingPattern", 224: "ClassPattern", 225: "TypeAlias", 226: "ImportMeta",
    227: "ImportFromMeta", 228: "ImportAllMeta", 229: "TString",
}


def read_int(b, p):
    first = b[p]
    p += 1
    if first == 15:
        v, p = read_int(b, p)
        n = v >> 1
        val = int.from_bytes(b[p:p + n], "little")
        return (-val if v & 1 else val), p + n
    if first & 1 == 0:
        return (first >> 1) - 10, p
    if first & 2 == 0:
        return (b[p] << 6) + (first >> 2) - 100, p + 1
    return ((b[p + 1] | (b[p + 2] << 8)) << 13) + (b[p] << 5) + (first >> 3) - 10000, p + 3


def items(b):
    """The stream as (offset, text) items: tags with their values, best effort."""
    out = []
    p = 0
    while p < len(b):
        start = p
        t = b[p]
        p += 1
        try:
            if t == 3:
                v, p = read_int(b, p)
                text = str(v)
            elif t == 4:
                n, p = read_int(b, p)
                text = repr(b[p:p + n].decode("utf-8", "replace"))
                if len(text) > 60:
                    text = text[:40] + "..." + text[-16:]
                p += n
            elif t == 20:
                n, p = read_int(b, p)
                text = f"list[{n}]"
            elif t == 21:
                n, p = read_int(b, p)
                vals = []
                for _ in range(n):
                    v, p = read_int(b, p)
                    vals.append(v)
                text = f"ints{vals}"
            elif t == 30:
                n, p = read_int(b, p)
                text = f"dict[{n}]"
            elif t == 6:
                text = repr(struct.unpack("<d", b[p:p + 8])[0])
                p += 8
            elif t == 152:
                vals = []
                for _ in range(4):
                    v, p = read_int(b, p)
                    vals.append(v)
                text = f"@{vals[0]}:{vals[1]}+{vals[2]}:{vals[3]}"
            else:
                text = TAGS.get(t, f"tag{t}")
        except IndexError:
            out.append((start, "<truncated>"))
            break
        out.append((start, text))
    return out


def first_difference(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n if len(a) != len(b) else -1


def describe(port, ext, label):
    """A readable account of the first difference of two byte strings."""
    off = first_difference(port, ext)
    lines = [f"  {label}: first difference at byte {off} (port {len(port)} bytes, extension {len(ext)})"]
    for name, data in (("port", port), ("ext ", ext)):
        its = items(data)
        k = 0
        while k < len(its) and its[k][0] <= off:
            k += 1
        k = max(k - 1, 0)
        window = its[max(k - 8, 0):k + 6]
        text = " ".join(("[" + t + "]") if o == its[k][0] else t for o, t in window)
        lines.append(f"    {name}: {text}")
    return "\n".join(lines)


def compare(port_result, ext_result):
    """None if equal, else a description of the first differing element."""
    names = ["ast bytes", "errors", "type ignores", "imports bytes", "ast data"]
    if port_result[0] == "exception" or ext_result[0] == "exception" or len(port_result) != len(ext_result):
        if port_result == ext_result:
            return None
        return f"  outcome: port {port_result!r}\n           ext  {ext_result!r}"
    for i, name in enumerate(names):
        a = port_result[i]
        b = ext_result[i]
        if a != b:
            if isinstance(a, bytes) and isinstance(b, bytes):
                return describe(a, b, name)
            if i == 1 and isinstance(a, list) and isinstance(b, list):
                for j in range(max(len(a), len(b))):
                    x = a[j] if j < len(a) else None
                    y = b[j] if j < len(b) else None
                    if x != y:
                        return f"  errors[{j}]: port {x!r}\n             ext  {y!r}"
            if i == 4 and isinstance(a, dict) and isinstance(b, dict):
                for key in sorted(set(a) | set(b)):
                    if a.get(key) != b.get(key):
                        return f"  ast data[{key!r}]: port {a.get(key)!r}\n             ext  {b.get(key)!r}"
            return f"  {name}: port {a!r}\n         ext  {b!r}"
    return None


def python_files(paths):
    for path in paths:
        p = Path(path)
        if p.is_dir():
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for f in sorted(files):
                    if f.endswith((".py", ".pyi")):
                        yield Path(root) / f
        else:
            yield p


LAST_TRACEBACK = [""]


def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # (the outcome, compared too)
        import traceback
        LAST_TRACEBACK[0] = "".join(traceback.format_exception(e)[-4:])
        return ("exception", type(e).__name__, str(e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--options", default="default")
    ap.add_argument("--source", choices=["none", "str", "bytes"], default="none")
    ap.add_argument("--limit", type=int, default=0, help="stop after N mismatches per option set")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--type-strings", action="store_true")
    args = ap.parse_args()
    if importlib.metadata.version("ast_serialize") != "0.13.1":
        sys.exit(f"ast_serialize {importlib.metadata.version('ast_serialize')} is installed; this checks 0.13.1")
    port = load()
    files = list(python_files(args.paths))
    names = list(OPTION_SETS) if args.options == "all" else args.options.split(",")
    failed = False
    for opt_name in names:
        kwargs = OPTION_SETS[opt_name]
        counts = {"clean": 0, "clean_same": 0, "errors": 0, "errors_same": 0}
        mismatches = 0
        t_port = 0.0
        t_ext = 0.0
        for f in files:
            if args.source == "none":
                src = None
            else:
                data = f.read_bytes()
                if args.source == "bytes":
                    src = data
                else:
                    try:
                        src = data.decode()
                    except UnicodeDecodeError:
                        continue
            t0 = time.perf_counter()
            ext_result = call(rust.parse, str(f), src, **kwargs)
            t1 = time.perf_counter()
            port_result = call(port.parse, str(f), src, **kwargs)
            t2 = time.perf_counter()
            t_ext += t1 - t0
            t_port += t2 - t1
            clean = isinstance(ext_result, tuple) and len(ext_result) == 5 and not ext_result[1]
            key = "clean" if clean else "errors"
            counts[key] += 1
            diff = compare(port_result, ext_result)
            if diff is None:
                counts[key + "_same"] += 1
                continue
            if clean:
                failed = True
            mismatches += 1
            if not args.quiet and (args.limit == 0 or mismatches <= args.limit):
                print(f"MISMATCH [{opt_name}] {f}{'' if clean else ' (extension reports syntax errors)'}")
                print(diff)
                if port_result[0] == "exception":
                    print(LAST_TRACEBACK[0])
        print(f"[{opt_name}] files without syntax errors: {counts['clean_same']}/{counts['clean']} identical; "
              f"with syntax errors: {counts['errors_same']}/{counts['errors']} identical "
              f"(port {t_port:.1f}s, extension {t_ext:.1f}s)")
    if args.type_strings:
        failed |= check_type_strings(port, files, args)
    sys.exit(1 if failed else 0)


TYPE_STRING_CASES = [
    "int", "List[int]", "Dict[str, int]", "int | None", "None", "a.b.C", "Callable[[int], str]",
    "Tuple[()]", "Tuple[int, ...]", "Literal['a', 1, -2, True, None, b'x']", "1 + 2", "", " ", "x y",
    "(int)", "'int'", "List['int']", "*Ts", "Unpack[Ts]", "f(x)", "lambda: 1", "[int, str]", "{'a': int}",
    "int | str | bytes", "Optional[\"Foo\"]", "é", "List[é]", "x.y[z]", "3.5", "-3", "+3", "--3", "~3",
    "not x", "a if b else c", "...", "Annotated[int, Arg(int, 'x')]", "Callable[[Arg(int, 'x'), DefaultArg(str)], None]",
    "Callable[[VarArg(int), KwArg(str)], None]", "type[int]", "x[1:2]", "def", "(", ")", "\\", "\n",
    "int  # comment", "int\nstr", "f'x'", "u'x'", "18446744073709551616", "Literal[18446744073709551615]",
    "Literal[0x10]", "Literal[1_000]", "x[]", "x[*Ts]", "x[int,]", "(int, str)", "int, str",
]


def harvest_type_strings(files):
    """String annotations and the texts of type comments of the files (via CPython's ast)."""
    import ast
    import io
    import tokenize
    out = []
    for f in files:
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        for node in ast.walk(tree):
            ann = []
            if isinstance(node, ast.AnnAssign):
                ann.append(node.annotation)
            elif isinstance(node, ast.arg) and node.annotation is not None:
                ann.append(node.annotation)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.returns is not None:
                ann.append(node.returns)
            for a in ann:
                for sub in ast.walk(a):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        out.append((sub.value, (sub.lineno, sub.col_offset, sub.end_lineno, sub.end_col_offset)))
        try:
            for tok in tokenize.generate_tokens(io.StringIO(src).readline):
                if tok.type == tokenize.COMMENT and "type:" in tok.string:
                    text = tok.string.split("type:", 1)[1].strip()
                    out.append((text, (tok.start[0], tok.start[1], tok.end[0], tok.end[1])))
        except (tokenize.TokenError, SyntaxError):
            pass
    return out


def check_type_strings(port, files, args):
    cases = [(c, (1, 2, 3, 4)) for c in TYPE_STRING_CASES] + harvest_type_strings(files)
    same = 0
    failed = False
    for cv in (0, 5, 7):
        for text, rng in cases:
            a = call(port.parse_type_string, text, rng, cache_version=cv)
            b = call(rust.parse_type_string, text, rng, cache_version=cv)
            if a == b:
                same += 1
                continue
            failed = True
            if not args.quiet:
                print(f"MISMATCH parse_type_string({text!r}, {rng}, cache_version={cv})")
                if isinstance(a, bytes) and isinstance(b, bytes):
                    print(describe(a, b, "type"))
                else:
                    print(f"  port {a!r}\n  ext  {b!r}")
    print(f"parse_type_string: {same}/{3 * len(cases)} identical ({len(cases)} strings, cache versions 0, 5, 7)")
    return failed


if __name__ == "__main__":
    main()
