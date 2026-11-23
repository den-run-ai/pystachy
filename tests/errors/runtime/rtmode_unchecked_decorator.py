# error: runtime.py may hold only functions, imports and docstrings at module level
import _rt


def twice(f: int) -> int:
    return f


@_rt.unchecked
@twice
def pys_sum_words(p: _rt.Ptr, n: int) -> int:
    return _rt.word(p, n) + 1
