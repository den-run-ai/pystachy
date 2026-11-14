# Membership of an optional str in list, tuple and set displays that hold None.
STRING_DELIMITERS: list[str] = ['"', "'"]


def get(s: str, i: int) -> str | None:
    if i < len(s):
        return s[i]
    return None


def f(s: str, i: int, closing: str) -> list[bool]:
    c = get(s, i)
    out: list[bool] = []
    out.append(c in STRING_DELIMITERS)
    out.append(c in ["}", None])
    out.append(c not in {",", "}", None})
    out.append(c is None or c in [closing, "}"])
    out.append(c in [closing, "}"])
    out.append(c not in [":", ","])
    out.append(c in (",", ":", None))
    out.append((c or "").lower() == "a")
    return out


print(f('"x', 0, "]"))
print(f('}x', 0, "]"))
print(f('', 0, "]"))
print(f(']', 0, "]"))
