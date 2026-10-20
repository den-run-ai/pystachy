# d[k] with a key that may be None: None is no key, so KeyError: None


def get(c: bool) -> str | None:
    return "a" if c else None


d = {"a": 1}
print(d[get(True)])
print(d[get(False)])
