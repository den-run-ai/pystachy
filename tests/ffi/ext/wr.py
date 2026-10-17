# the idiom open(...).write(...) through pyobj: the file object is dropped; the host's exit releases
# it (atexit), so its data reaches the file as under CPython
from ffi import export
from pyobj import import_module, of_str, Object

_kept: list[Object] = []


@export
def save(path: str, text: str) -> None:
    import_module("builtins").attr("open").call([of_str(path), of_str("w")]).attr("write").call([of_str(text)])


@export
def log(path: str, text: str) -> None:
    if len(_kept) == 0:
        _kept.append(import_module("builtins").attr("open").call([of_str(path), of_str("w")]))
    _kept[0].attr("write").call([of_str(text)])
