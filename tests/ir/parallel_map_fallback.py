from parallel import map_float

seen: list[float] = []


def unsafe(x: float) -> float:
    seen.append(x)
    return x * x


def division(x: float) -> float:
    return x / 2.0


print(map_float(unsafe, [1.0, 2.0], 4))
print(map_float(division, [1.0, 2.0], 4))
