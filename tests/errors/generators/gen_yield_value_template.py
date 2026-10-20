# error: cannot send str to Generator[int], whose send type is None: annotate its generator function -> Generator[Y, S, R]
def echo():
    while True:
        s = yield 1
        print(s)


g = echo()
next(g)
g.send("hi")
