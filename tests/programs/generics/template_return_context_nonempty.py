# Fresh heterogeneous displays can use their caller's result context. Values
# retain their scalar tags, including integers above float's exact range.
def pair(a, b):
    return [a, b]


def mapping(a, b):
    return {"first": a, "second": b}


def forward(a, b):
    return pair(a, b)


def integer() -> int:
    print("integer")
    return 9007199254740993


def decimal() -> float:
    print("decimal")
    return 2.5


xs: list[int | float] = pair(integer(), decimal())
ys: list[int | float | str] = pair(9007199254740993, 2.5)
zs: list[int | float | str] = forward(9007199254740993, 2.5)
xs.append(7)
ys.append("wide")
print(xs, ys, zs)
print(isinstance(xs[0], int), isinstance(xs[1], float), xs[0] == 9007199254740993)
print(isinstance(ys[0], int), isinstance(ys[1], float))

values: dict[str, int | float] = mapping(9007199254740993, 2.5)
wide_values: dict[str, int | float | str] = mapping(9007199254740993, 2.5)
wide_values["third"] = "wide"
print(values, wide_values)
print(isinstance(values["first"], int), values["first"] == 9007199254740993)

mixed: list[int | float] | str = pair(1, 2.5)
print(mixed)
print(pair(1, 2))  # an independent call retains homogeneous inference


def consume(values: list[int | float]) -> None:
    print(values)


def annotated() -> list[int | float]:
    return pair(1, 2.5)


consume(pair(1, 2.5))
print(annotated())


def maybe(flag, a, b):
    if flag:
        return None
    return [a, b]


absent: list[int | float] | None = maybe(True, 1, 2.5)
present: list[int | float] | None = maybe(False, 1, 2.5)
print(absent, present)
