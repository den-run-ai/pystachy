# Iterating .items() or .values() of **kwargs where a call passes no extra keyword arguments
# (#240): the loop, or the comprehension, never runs, as CPython's over an empty dict. Its body
# is compiled for that call only where **kwargs: T gives the values a type, as one over () is not.


def comp(**kw) -> list[str]:
    return [k + "=" + str(v) for k, v in kw.items()]


def loop(**kw) -> list[str]:
    out: list[str] = []
    for k, v in kw.items():
        out.append(k + "=" + str(v))
    return out


print(comp(a=1), comp())
print(loop(a=1), loop())
print(comp(a=1, b=2), loop(x="s", y="t"))


def annotated(**kw: int) -> int:
    total = 0
    for v in kw.values():
        total += v
    return total


print(annotated(a=1, b=2), annotated())


def joined(**kw) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in kw.items())


print(repr(joined(a=1, b=2)), repr(joined(s="x")), repr(joined()))


def sums(**kw: int) -> int:
    return sum(v for v in kw.values())


print(sums(a=4, b=5), sums())


def tests(**kw: int) -> str:
    return str(any(v > 3 for v in kw.values())) + " " + str(all(v > 3 for v in kw.values()))


print(tests(a=4), tests(a=1, b=9), tests())


def with_else(**kw) -> str:
    for k, v in kw.items():
        if k == "stop":
            print("break at", v)
            break
    else:
        return "no break"
    return "broke"


print(with_else(a=1), with_else(stop=2), with_else())


def keys_and_values(**kw: str) -> str:
    names = [k for k in kw.keys()]
    vals = sorted({v for v in kw.values()})
    lens = list(len(v) for v in kw.values())
    return str(names) + " " + str(vals) + " " + str(lens)


print(keys_and_values(a="xy", b="z"), keys_and_values())


def nested(**kw) -> list[str]:
    out: list[str] = []
    for i in range(2):
        for k, v in kw.items():
            out.append(str(i) + k + str(v))
    return out


print(nested(a=1), nested())


def body_only_for_str(**kw) -> list[str]:
    # (its body compiles only for str values: never for a call without them)
    return [v.upper() for v in kw.values()]


print(body_only_for_str(a="x"), body_only_for_str())


def forward(**kw) -> list[str]:
    return comp(**kw) + loop(**kw)


print(forward(z=26), forward())
