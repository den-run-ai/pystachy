# error: _rt.words() takes the count of words, from 1 to 16, as an int literal
import _rt


def pys_scratch(n: int) -> int:
    w = _rt.words(n)
    _rt.put(w, 0, n)
    return _rt.word(w, 0)
