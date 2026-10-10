import helper


class MyErr(Exception):
    pass


def ident(x):
    return x


def flag(b: bool) -> bool:
    return not b


def tup(t: tuple[int, float, str]) -> tuple[str, int]:
    return (t[2], t[0])


def maybe(x: float | None) -> float | None:
    return x


p = helper.Pt(3, True)
print(helper.scale(p, 2), ident(5), ident("s"), flag(True), tup((1, 2.0, "z")), maybe(None), helper.TABLE)
try:
    raise MyErr("bad")
except MyErr as e:
    print(e)
