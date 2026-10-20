"""Container equality and search compare payloads, including numeric cross-types."""
values: list[int | str | None] = [1, "one", None, 0, "", 1]
same: list[int | str | None] = [1, "one", None, 0, "", 1]
print(values == same, values != same)
print({"values": values} == {"values": same})
print((values, "end") == (same, "end"))

def query(v: int | float | bool | str | None) -> None:
    print(repr(v), v in values, v not in values, values.count(v))
    try:
        print(values.index(v), values.index(v, -5, 20))
    except ValueError as error:
        print(str(error))

queries: list[int | float | bool | str | None] = [True, False, 1.0, 2.5, "one", "missing", None]
for v in queries:
    query(v)
print(True in values, values.count(1.0), values.index(None))
values.remove(True)
values.remove(0.0)
values.remove(None)
print(values)
try:
    values.remove("absent")
except ValueError as error:
    print(str(error))

def in_tuple(v: int | str) -> bool:
    return v in (False, 3, "yes", None)

print(in_tuple(3), in_tuple("yes"), in_tuple("no"))

# Aliases retain the same mutable container, while boxes preserve old snapshots.
alias = values
old = values[0]
alias[0] = 42
print(alias is values, old, values)
for i in range(160):
    values.append(str(i) * 20)
print(old, values[0], values[-1], values.count(42.0))

# Distinct NaNs compare unequal in both runtimes (same-object NaN is a documented deviation).
nan: float | str = float("nan")
nans: list[float | str] = [float("nan"), "nan"]
print(nan == nan, nan in nans, nans.count(nan), "nan" in nans)
