# An optional import of a module whose code raises ImportError at its top level (also after a
# platform test): its code runs up to the raise, then the handler; the module is not imported, so
# each import runs its code again (issue #4, reproduction E, first). A failing package stops the
# import of its submodule. The last import is not optional, and ends the program.
try:
    import loader.broken
except ImportError:
    print("fallback")
try:
    import loader.winonly
except ImportError:
    print("no winonly")
try:
    from loader.winonly import f
except ImportError:
    def f() -> int:
        return 2
print(f())
try:
    import loader.pkg.bad
except ModuleNotFoundError:
    print("no pkg.bad")
try:
    import loader.fpkg.sub
except ImportError:
    print("no fpkg")
try:
    import loader.noisy
except ImportError:
    print("no noisy")
import loader.lazy
print(loader.lazy.load(), loader.lazy.load())


def load() -> str:
    try:
        import loader.broken
    except ImportError:
        return "fallback"
    return "ok"


print(load())
import loader.winonly
print("not reached")
