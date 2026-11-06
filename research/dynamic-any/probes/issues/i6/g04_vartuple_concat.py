def join(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[str, ...]:
    return a + b


k: tuple[str, ...] = ("a",)
k += ("b",)
print(join(k, ("c",)))
