# d.pop(k) with a key that is None and no default: KeyError: None


def get(c: bool) -> str | None:
    return "a" if c else None


d = {"a": 1}
print(d.pop(get(False)))
