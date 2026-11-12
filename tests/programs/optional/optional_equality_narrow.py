# A comparison with a constant, or membership in a list of them, that holds shows an optional
# str or number is not None, as type checkers narrow it.
def get(s: str, i: int) -> str | None:
    if i < len(s):
        return s[i]
    return None


def num(s: str) -> int | None:
    if s.isdigit():
        return int(s)
    return None


def up(c: str) -> str:
    return c.upper()


def f(s: str) -> str:
    c = get(s, 0)
    out = ""
    if c == "a":
        out += up(c)
    if "b" == c:
        out += up(c)
    if len(s) > 0 and c == "c":
        out += up(c)
    if c in ["d", "e"]:
        out += up(c)
    if c in ("f", "g") and len(s) > 1:
        out += up(c) + up(c)
    if c in {"h"}:
        out += up(c)
    if not (c != "i"):
        out += up(c)
    if c != "j" or len(s) == 9:
        out += "-"
    else:
        out += up(c)
    if c not in ["k", "l"]:
        out += "."
    else:
        out += up(c)
    while c == "m":
        out += up(c)
        c = None
    n = num(s)
    if n == 5:
        out += str(n + 1)
    if n in (7, 8):
        out += str(n * 2)
    return out


for text in ["a", "b", "c", "dx", "e", "f", "gg", "h", "i", "j", "k", "l", "m", "", "5", "7", "8", "zz"]:
    print(repr(text), f(text))

DELIMS: list[str] = ['"', "'"]
KEYS = {"x": 1}


def g(s: str) -> str:
    c = get(s, 0)
    local = {"q", "r"}
    out = ""
    if c in DELIMS:
        out += up(c)
    if c in KEYS:
        out += up(c)
    if c in local:
        out += up(c) * 2
    if c not in DELIMS:
        out += "!"
    else:
        out += up(c)
    return out


for text in ['"', "'", "x", "q", "", "z"]:
    print(repr(text), g(text))
