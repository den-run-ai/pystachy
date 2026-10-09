# error: runtime.py's functions cannot use global variables
def pys_rt_t(s: str) -> str:
    global LAST
    LAST = s
    return s
