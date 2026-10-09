# error: in runtime.py, a parameter's default value must be a literal (in pad())
def pad(s: str, fill: str = " " * 2) -> str:
    return s + fill


def pys_rt_t(s: str) -> str:
    return pad(s)
