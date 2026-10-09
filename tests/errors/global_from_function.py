# error: a function assigns it, so declare it at module level first (g: T)
def setg(v):
    global g
    g = v


print(g)
setg(5)
