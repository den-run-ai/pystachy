# In a namespace package (tests/extless/extless_ns, a directory without __init__.py), a text file
# without the .py suffix is no submodule either (#1166), while the directory's .py modules are.
try:
    import extless_ns.plain
    print("imported extless_ns.plain")
except ImportError:
    print("fallback: no module extless_ns.plain")
import extless_ns.mod
print(extless_ns.mod.VALUE)
