# error: _rt.get(): List.a holds an address: read it with _rt.getp and write it with _rt.setp
import _rt


def pys_list_first(l: _rt.Ptr) -> int:
    return _rt.word(_rt.ptr(_rt.get(l, "List.a")), 0)
