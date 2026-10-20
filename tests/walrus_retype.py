# x := v gives x a value of another type than its first: x holds their union, as x = v
# does (CPython: x holds the str from there on).


def f() -> None:
    x = 1
    print((x := "s"), x)


f()
