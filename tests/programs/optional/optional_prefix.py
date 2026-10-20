# try: <imports> / except ImportError: the imports before the one that fails run, with their
# modules' code and what they bind, before the handler (issue #4, reproduction D, first); where a
# submodule is missing, its packages' code runs first, and an import binds nothing if it fails.
try:
    import loader.helper
    import loader.unavailable
except ImportError:
    print("fallback")
print(loader.helper.V)
try:
    import loader.helper, unavailable2
except ImportError:
    print("fallback 2")
try:
    import loader.pkg.missing
except ImportError:
    print("fallback 3")
try:
    from nothere import thing
except ModuleNotFoundError:
    thing = 5
print(thing)
try:
    import loader.pkg.missing as pm
except ImportError:
    pm_ok = False
print(pm_ok)
import loader.rel
print(loader.rel.y)


def f() -> int:
    try:
        from loader.helper import V
        import unavailable3
    except ImportError:
        print("fallback in f")
    return V


print(f())
