def codepoint(s: str, i: int) -> int:
    return ord(s[i])


def from_list(chars: list[str], i: int) -> int:
    return ord(chars[i])


def from_slice(s: str, i: int) -> int:
    return ord(s[i:i + 1])


print(codepoint("αβ", -1), from_list(["x"], 0), from_slice("ab", 1))
