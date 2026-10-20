# error: kwargs_annotation.py:6: error: expected int, got str
def g(**kw: int) -> int:
    return len(kw)


print(g(x="bad"))
