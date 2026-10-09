# error: pys_str_partition() is defined as tuple[str,str](str, str), but the compiler calls it as tuple[str,str,str](str, str) (RUNTIME's str.partition)
def pys_str_partition(s: str, sep: str) -> tuple[str, str]:
    return (s, sep)
