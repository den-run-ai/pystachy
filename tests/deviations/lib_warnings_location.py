# Deviation: warnings.warn() shows a warning at "<sys>", line 0, as Pystachy has no frames
# (sys._getframe()): CPython gives that location where the stack is shallower than stacklevel,
# and otherwise the file and line of the code that warns, with its source line. Every warning is
# the main program's: its module is "__main__" and its registry the main program's, so the
# default action shows a text and category once in the program, where CPython shows it once per
# location. A registry's keys are (text, category, lineno) tuples, also its filters version's,
# with 1 for True; the default filter's module is the pattern __main__\Z, which matches only the
# module __main__, where CPython's C module keeps the str "__main__"
import warnings


def old() -> None:
    warnings.warn("old() is deprecated", DeprecationWarning, stacklevel=2)


warnings.warn("shown")
old()
warnings.warn("twice")
warnings.warn("twice")
reg: dict[tuple[str, type[Warning], int], int] = {}
warnings.warn_explicit("explicit", UserWarning, "f.py", 3, "f", reg)
print(type(list(reg)[0]).__name__, reg[("explicit", UserWarning, 3)])
print(warnings.filters[0])
