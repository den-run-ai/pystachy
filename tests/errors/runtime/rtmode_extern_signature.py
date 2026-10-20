# error: pys_str_find() is declared as i64(ptr, ptr), but the compiler calls it as i64(ptr, ptr, i64, i64) (RUNTIME's str.find)
def pys_str_find(s: str, sub: str) -> int: ...


def pys_rt_t(s: str) -> int:
    return pys_str_find(s, "x")
