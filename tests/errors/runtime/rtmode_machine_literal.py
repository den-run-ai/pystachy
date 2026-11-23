# error: _rt.get() takes the field, as Record.field, as a str literal
import _rt


def pys_field_of(l: _rt.Ptr, name: str) -> int:
    return _rt.get(l, name)
