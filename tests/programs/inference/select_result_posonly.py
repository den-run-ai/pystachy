# A positional-only selector's name given as a keyword is a **kwargs key: the selector keeps its
# default there, and only an argument by position chooses.
def pick(x: int, flag=False, /, **kw):
    if flag:
        return [x, len(kw)]
    return x


print(pick(1, flag=True), pick(2, True), pick(3), pick(4, True, flag=False))
