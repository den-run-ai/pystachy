# error: runtime function pys_rt_t() takes or returns bool: the runtime ABI passes bools as int
def pys_rt_t(s: str) -> bool:
    return s == ""
