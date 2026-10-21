# error: cannot infer the type of 'REG', an empty dict so far: annotate it (REG: dict[K, V] = {})
# (the function that fills it stores an empty list, which shows nothing of what REG holds)
REG = {}


def add(k: str, v: int) -> None:
    if k not in REG:
        REG[k] = []
    REG[k].append(v)


print(REG)
add("a", 1)
print(REG)
