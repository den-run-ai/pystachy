# error: 'strlen' declares a C function: in runtime.py that is one of runtime.c's, named pys_*
def strlen(s: str) -> int: ...


def pys_rt_t(s: str) -> int:
    return strlen(s)
