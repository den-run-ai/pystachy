# error: a function assigns it, so declare it at module level first (g: T)
def getg() -> int:
    return g


def setg() -> None:
    global g
    g = 5


setg()
print(getg())
