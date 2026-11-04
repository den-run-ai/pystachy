def at(s: str, index: int | None) -> int:
    return ord(s[index])


text = "é中🚀"


def rebind() -> int:
    global text
    text = "after"
    return -1


print(ord(text[rebind()]), text)
for s in ["", "ascii", "\x00é中🚀", chr(0xD800)]:
    chars = list(s)
    for i in range(-len(chars), len(chars)):
        assert at(s, i) == ord(chars[i])
    for i in [-9223372036854775808, -len(chars) - 1, len(chars), 9223372036854775807]:
        try:
            at(s, i)
        except IndexError as exc:
            assert str(exc) == "string index out of range"
        else:
            assert False

try:
    at("a", None)
except TypeError as exc:
    print(str(exc))

print(ord(text[True]))


def shadowed() -> int:
    def ord(s: str) -> int:
        return len(s)
    return ord("xy")


print(ord("/"), ord("\x00"), ord("é"), ord("中"), ord("🚀"), ord("\ud800"), shadowed())
try:
    ord("")
except TypeError as exc:
    print(str(exc))
try:
    ord("e\u0301")
except TypeError as exc:
    print(str(exc))

pair = (2, 3)
try:
    print(pair[ord("/")])
except IndexError as exc:
    print(str(exc))
