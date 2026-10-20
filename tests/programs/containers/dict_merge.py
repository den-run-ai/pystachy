# Dict displays with **: of **kwargs records (and str keys) a record of the merged keyword
# arguments, a name keeping its first place and taking its last value; of dicts of one type a
# new dict, each ** updating it once its operand is evaluated, in CPython's order
def note(s: str) -> str:
    print("eval", s)
    return s


def show(**kw):
    return kw


def merged(**kw):
    both = {**kw, "x": 9, **show(y="é")}
    print(both, len(both), "x" in both, both["x"])
    return show(**{"z": 0, **kw})


print(merged(a=1, x="old"))
print(merged())


def override(a: int, b: str = "-") -> str:
    return f"{a}{b}"


def forward(**kw):
    return override(**{**kw, "a": 2})


print(forward(a=1), forward(b="+"))

d1 = {"a": 1, "b": 2}
d2 = {"b": 3, "c": 4}
print({**d1, **d2}, {**d2, **d1}, {"z": 0, **d1, "a": 5}, {**d1})
m = {**d1}
m["q"] = 7
print(m, d1)
print({note("k"): 1, **{note("j"): 2}, note("i"): 3})
src = {"a": 1}
print({**src, "x": src.pop("a")}, src)
opt: dict[str, int] | None = None
for v in [d1, opt]:
    try:
        print({**{"base": 0}, **v})
    except TypeError as e:
        print("TypeError:", e)
