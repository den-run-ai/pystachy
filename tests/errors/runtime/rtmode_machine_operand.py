# error: _rt.word() takes (a reference, int), not (int, int)
import _rt


def pys_word_of(a: int, i: int) -> int:
    return _rt.word(a, i)
