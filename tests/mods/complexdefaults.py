"""Module for tests/programs/imports/complex_default_dynany.py and
tests/errors/imports/complex_default_needed.py: defs that annotate a parameter complex, whose
defaults run when the defs do; one of another type (z: complex = 0) is an error only where a call
needs it. From claude/blissful-hawking-ve4fwg-complex (#1414)."""


def note(text: str) -> int:
    print("default", text)
    return len(text)


def scaled(x: float, factor: complex = note("factor")) -> complex:
    return x * factor


def shifted(z: complex, by: complex = complex(note("by"), 1)) -> complex:
    return z + by


def plain(z: complex = 0) -> complex:
    return z


def doubled(z: complex) -> complex:
    return z * 2
