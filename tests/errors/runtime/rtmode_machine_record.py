# error: _rt.set(): 'List.size' is no field of a record of the runtime (RTRECORDS)
import _rt


def pys_list_resize(l: _rt.Ptr, n: int) -> None:
    _rt.set(l, "List.size", n)
