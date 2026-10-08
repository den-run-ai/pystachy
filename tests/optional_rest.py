# An optional import is decided at compile time, so what runs in its try must not raise
# ImportError otherwise; but only what runs there counts: the statements after the imports (a
# flag), what the imported module's code runs (not the bodies of its functions), and functions
# only where that code may call one.
try:
    import loader.checks

    HAVE = True
except ImportError:
    HAVE = False


def require(flag: bool) -> None:
    if not flag:
        raise ImportError("loader.checks is required")


require(HAVE)
if not HAVE:
    raise ImportError("loader.checks is required")
print(HAVE, loader.checks.need(3))
try:
    import loader.helper

    print("helper imported", 1, end="!\n")
except ImportError:
    print("fallback")
loader.checks.need(-1)
