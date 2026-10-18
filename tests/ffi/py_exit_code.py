# A SystemExit that Python code raises keeps its str() and repr(), and its code the status that
# CPython's own exit gives it (an int beyond 64 bits -1, an int subclass its value); GeneratorExit
# and other BaseExceptions are no Exception
from pyobj import import_module, of_str

builtins = import_module("builtins")
run = builtins.attr("exec")
for src in ["raise SystemExit(2**70)", "raise SystemExit(-2**63 - 1)", "raise SystemExit(True)", "raise SystemExit(None)",
            "raise SystemExit()", "raise SystemExit('bye')", "raise SystemExit(2.5)", "raise SystemExit(1, 2)",
            "import sys; sys.exit((3,))", "import signal; raise SystemExit(signal.SIGTERM)"]:
    try:
        run.call([of_str(src), builtins.attr("dict").call([])])
    except SystemExit as e:
        print(src, "->", str(e), repr(e))
for src in ["raise GeneratorExit('g')", "class B(BaseException): pass\nraise B('b')"]:
    try:
        run.call([of_str(src), builtins.attr("dict").call([])])
    except Exception:
        print("an Exception:", src)
    except BaseException as e:
        print(src[src.rfind("\n") + 1 :], "->", repr(e))
run.call([of_str("import signal; raise SystemExit(signal.SIGTERM)"), builtins.attr("dict").call([])])
print("not reached")
