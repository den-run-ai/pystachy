# pystachy: dynamic-any
# Selected functions from CPython v3.13.16 Lib/copyreg.py, PSF license.
# Upstream SHA-256: c8eda41f05c6bf95a4da4726a530409d2485ae060b8d019b3a8034389a15d3e9
# Pystachy port: opt into dynamic Any and annotate the registry's empty storage.
# Registration function bodies are unchanged; this is not a complete copyreg port.
from typing import Any

dispatch_table: dict[Any, Any] = {}

def pickle(ob_type, pickle_function, constructor_ob=None):
    if not callable(pickle_function):
        raise TypeError("reduction functions must be callable")
    dispatch_table[ob_type] = pickle_function

    # The constructor_ob function is a vestige of safe for unpickling.
    # There is no reason for the caller to pass it anymore.
    if constructor_ob is not None:
        constructor(constructor_ob)

def constructor(object):
    if not callable(object):
        raise TypeError("constructors must be callable")
