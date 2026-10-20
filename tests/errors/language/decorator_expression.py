# error: unsupported decorator: only a dotted name or a call of one is supported (PEP 614)
@(lambda f: f)
def g() -> int:
    return 1


print(g())
