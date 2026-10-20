# warnings (lib/warnings.py, adapted CPython): warn() and warn_explicit() through the filters and
# their actions, catch_warnings() (record=True, action=...), simplefilter(), filterwarnings() by
# message, category, module and line, resetwarnings(), formatwarning(), showwarning() to a file,
# categories of the program, warnings given as objects, the registries of the default, module and
# once actions, _deprecated(), and the errors of bad arguments. A warning that warn() shows has no
# location here (tests/deviations/lib_warnings_location.py), so this program records those;
# warn_explicit() names one, as the last warning, shown on stderr, does
import sys
import warnings


class AppWarning(UserWarning):
    pass


class OtherWarning(Warning):
    pass


def noisy(n: int) -> int:
    warnings.warn(f"noisy {n}", AppWarning, stacklevel=2)
    return n


def show(what: str, log) -> None:
    print(what, len(log), [(m.category.__name__, str(m.message)) for m in log])


with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("always")
    noisy(1)
    noisy(2)
    warnings.warn("plain")
    warnings.warn("old", DeprecationWarning)
    warnings.warn(FutureWarning("an object"))
    warnings.warn(AppWarning("of the program"), RuntimeWarning)
    warnings.warn("other", OtherWarning)
    show("always", log)
    for m in log:
        print(isinstance(m.message, Warning), m.category is type(m.message), issubclass(m.category, UserWarning), m.line)
    print(type(log[0].message).__name__, repr(log[0].message), str(log[0]).startswith("{message : AppWarning('noisy 1')"))
with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("default")
    for i in range(3):
        noisy(7)
        warnings.warn("loop", RuntimeWarning)
    show("default", log)
with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("once")
    for i in range(3):
        noisy(8)
        warnings.warn("other once", RuntimeWarning)
    noisy(8)
    show("once", log)
with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("module")
    for i in range(2):
        noisy(9)
    noisy(9)
    show("module", log)
with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("always")
    warnings.filterwarnings("ignore", message="noisy 1")
    warnings.filterwarnings("ignore", message="OTHER")
    warnings.filterwarnings("ignore", category=OtherWarning)
    warnings.filterwarnings("error", category=RuntimeWarning)
    warnings.filterwarnings("ignore", module="__main__", category=FutureWarning)
    warnings.filterwarnings("always", module="elsewhere", category=ImportWarning)
    noisy(1)
    noisy(10)
    noisy(2)
    warnings.warn("other text", UserWarning)
    warnings.warn("other", OtherWarning)
    warnings.warn("future", FutureWarning)
    warnings.warn("import", ImportWarning)
    try:
        warnings.warn("bad", RuntimeWarning)
    except RuntimeWarning as e:
        print("raised", repr(e), type(e) is RuntimeWarning)
    show("filtered", log)
n = len(warnings.filters)
with warnings.catch_warnings():
    warnings.simplefilter("ignore", AppWarning)
    warnings.simplefilter("ignore", AppWarning)
    print(len(warnings.filters) - n)
    noisy(3)
print(len(warnings.filters) == n)
with warnings.catch_warnings(action="error", category=AppWarning):
    try:
        noisy(4)
    except AppWarning as e:
        print("error action", e)
    try:
        noisy(5)
    except UserWarning as e:
        print("error action", repr(e))
with warnings.catch_warnings(record=True) as outer:
    warnings.simplefilter("always")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        warnings.warn("hidden", DeprecationWarning)
        warnings.warn("kept")
    with warnings.catch_warnings(record=True) as inner:
        warnings.warn("inner")
    warnings.warn("outer")
    show("outer", outer)
    show("inner", inner)
print(warnings.formatwarning("msg", UserWarning, "file.py", 12), end="")
print(warnings.formatwarning("msg", AppWarning, "file.py", 12, "  x = 1  "), end="")
print(warnings.formatwarning(AppWarning("w"), AppWarning, "f.py", 1, ""), end="")
warnings.showwarning("shown", RuntimeWarning, "f.py", 3, sys.stdout)
warnings.showwarning("shown with line", RuntimeWarning, "f.py", 4, sys.stdout, "y = 2")
reg: dict[tuple[str, type[Warning], int], int] = {}
with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("default")
    warnings.filterwarnings("ignore", lineno=6)
    for line in [5, 5, 6, 7]:
        warnings.warn_explicit("explicit", UserWarning, "mod.py", line, "mod", reg)
    warnings.warn_explicit(UserWarning("again"), UserWarning, "mod.py", 5, "mod", reg)
    warnings.warn_explicit("no registry", UserWarning, "x.py", 1)
    warnings.warn_explicit("no registry", UserWarning, "x.py", 1)
    print([(m.filename, m.lineno, str(m.message)) for m in log], len(reg))
    print(("explicit", UserWarning, 5) in reg, ("explicit", UserWarning, 6) in reg, ("again", UserWarning, 5) in reg)
with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("always")
    warnings._deprecated("thing", remove=(3, 15))
    warnings._deprecated("other", "{name!r} goes in {remove}", remove=(3, 16))
    warnings._deprecated("third", "{name} {{braces}} {remove!r:>6}", remove=(4, 0))
    show("deprecated", log)
try:
    warnings._deprecated("old", remove=(3, 12))
except RuntimeError as e:
    print("RuntimeError", e)
print(repr(warnings.catch_warnings()), repr(warnings.catch_warnings(record=True)))
cw = warnings.catch_warnings()
with cw:
    try:
        cw.__enter__()
    except RuntimeError as e:
        print("RuntimeError", e)
try:
    warnings.catch_warnings().__exit__(None, None, None)
except RuntimeError as e:
    print("RuntimeError", e)
for bad in ["bogus", "Error"]:
    try:
        warnings.simplefilter(bad)
    except ValueError as e:
        print("ValueError", e)
try:
    warnings.filterwarnings("ignore", lineno=-1)
except ValueError as e:
    print("ValueError", e)
try:
    warnings.warn("x", 5)
except TypeError as e:
    print("TypeError", e)
try:
    warnings.warn("x", skip_file_prefixes=["a"])
except TypeError as e:
    print("TypeError", e)
warnings.resetwarnings()
print(len(warnings.filters))
warnings.simplefilter("ignore")
warnings.warn("hidden")
print(warnings.filters[0][0], warnings.filters[0][2].__name__, len(warnings.filters))
warnings.simplefilter("always", UserWarning)
warnings.warn_explicit("to stderr", UserWarning, "virtual.py", 7)
