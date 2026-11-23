# error: pys_set_big_pop() returns two words (RUNTIME's set.big_pop is a promoting int): each of its returns must make the tuple of them
import _rt


def pair(s: _rt.Ptr) -> tuple[int, _rt.Ptr]:
    return 2, s


def pys_set_big_pop(s: _rt.Ptr) -> tuple[int, _rt.Ptr]:
    t = pair(s)
    return t
