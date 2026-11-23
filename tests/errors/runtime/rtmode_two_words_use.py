# error: helper() uses the result of pys_set_big_pop() as a tuple: a result of two words may only be unpacked
import _rt


def pys_set_big_pop(s: _rt.Ptr) -> tuple[int, _rt.Ptr]:
    return 1, _rt.nil()


def helper(s: _rt.Ptr) -> int:
    t = pys_set_big_pop(s)
    u = t
    return u[0]
