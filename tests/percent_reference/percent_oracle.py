"""CPython's own printf-style formatting, which tests/programs/strings/percent_runtime.py compares
lib/_pystachy_percent.py's percent_format() with: CPython has no _pystachy_percent, so the program
imports this module there."""


def percent_format(fmt, args):
    return fmt % args
