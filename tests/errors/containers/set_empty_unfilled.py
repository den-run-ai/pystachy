# error: cannot infer the type of 's', an empty set so far: annotate it (s: set[T] = set())
def f(n: int) -> None:
    s = set()
    print(sorted(s))
    for i in range(n):
        s.add(i * 2)


f(2)
