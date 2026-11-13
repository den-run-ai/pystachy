_UNSET = object()


def get(d: dict[str, str], key: str, fallback=_UNSET):
    if key in d:
        return d[key]
    if fallback is _UNSET:
        raise KeyError(key)
    return fallback


d = {"a": "1"}
print(get(d, "a"), get(d, "z", "dflt"), get(d, "z", None))
try:
    get(d, "z")
except KeyError as e:
    print("KeyError", e)
