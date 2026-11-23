# error: _rt.local() takes a record of the runtime (RTRECORDS) as a str literal
import _rt


def pys_scratch(n: int) -> int:
    b = _rt.local("Buffer")
    _rt.set(b, "Buf.n", n)
    return _rt.get(b, "Buf.n")
