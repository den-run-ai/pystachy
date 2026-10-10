from ffi import pycall


@pycall("json")
def dumps(obj: dict[str, int]) -> str: ...


@pycall("statistics")
def median(data: list[float]) -> float: ...


counts: dict[str, int] = {"a": 1, "b": 2}
print(dumps(counts))
print(median([3.0, 1.0, 2.0]))
