# error: runtime function pys_rt_t() needs an annotation on every parameter, and no *args
def pys_rt_t(a: int, *rest: int) -> int:
    return a
