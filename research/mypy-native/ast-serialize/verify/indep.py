# Independent check, not the subagent's tool: load lib/ast_serialize by path and compare
# parse() with the installed extension on files given on the command line
import importlib.util, sys, random, pathlib
import ast_serialize as real

assert "site-packages" in real.__file__, real.__file__
root = pathlib.Path("/home/user/wt-astser/lib/ast_serialize")
spec = importlib.util.spec_from_file_location("port_ast_serialize", root / "__init__.py", submodule_search_locations=[str(root)])
port = importlib.util.module_from_spec(spec)
sys.modules["port_ast_serialize"] = port
spec.loader.exec_module(port)
assert port.__file__.startswith("/home/user/wt-astser/"), port.__file__
assert port.parse is not real.parse

def run(m, *a, **k):
    try:
        return ("ok", m.parse(*a, **k))
    except Exception as e:
        return (type(e).__name__, str(e))

files = [l.strip() for l in open(sys.argv[1]) if l.strip()]
rng = random.Random(2026)
same = diff = errs = 0
first = None
for f in files:
    src = open(f, "rb").read()
    variants = [src]
    # two corruptions of my own: drop a random slice, and insert stray tokens
    if len(src) > 20:
        i = rng.randrange(len(src) - 10)
        variants.append(src[:i] + src[i + rng.randrange(1, 9):])
        j = rng.randrange(len(src))
        variants.append(src[:j] + rng.choice([b")", b"(", b":", b"'", b" lambda ", b"\n\t ", b"=", b"\\", b"{", b"f'{"]) + src[j:])
    for v in variants:
        for kw in [dict(), dict(skip_function_bodies=True, python_version=(3, 9), platform="win32", cache_version=5)]:
            a = run(real, f, v, **kw)
            b = run(port, f, v, **kw)
            if a[0] == "ok" and a[1][1]:
                errs += 1
            if a == b:
                same += 1
            else:
                diff += 1
                if first is None:
                    first = (f, kw, a[0], b[0], [x == y for x, y in zip(a[1], b[1])] if a[0] == b[0] == "ok" else (a[1] if a[0] != "ok" else "", b[1] if b[0] != "ok" else ""))
print("files", len(files), "comparisons", same + diff, "identical", same, "different", diff, "with syntax errors", errs)
print("first difference:", first)
