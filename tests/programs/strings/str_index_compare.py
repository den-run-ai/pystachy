def match(s: str, i: int) -> tuple[bool, bool, bool, bool]:
    return s[i] == ":", ":" == s[i], s[i] != ":", ":" != s[i]


def nul(s: str, i: int) -> bool:
    return s[i] == "\x00"


for text in [":a", "é:中\x00🚀", "\ud800"]:
    chars = list(text)
    for j in range(-len(chars), len(chars)):
        same = chars[j] == ":"
        assert match(text, j) == (same, same, not same, not same)
        assert nul(text, j) == (chars[j] == "\x00")

for j in [-9223372036854775808, -2, 1, 9223372036854775807]:
    try:
        match(":", j)
    except IndexError as exc:
        assert str(exc) == "string index out of range"
    else:
        assert False

original = "".join(["é", ":"])
calls = 0


def replace() -> int:
    global original, calls
    original = "."
    calls += 1
    return -1


print(":" == original[replace()], original, calls)
print(original[True - 1] != ":")


class Lookup:
    def __getitem__(self, index: int) -> str:
        print("lookup", index)
        return ":"


print(":" == Lookup()[4])
