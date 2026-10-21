# Locals first assigned None take T | None from the other values assigned to them: in any branch,
# before or after in the source, in loops and by unpacking; also module code's globals


# a global first assigned None, typed by module code's other assignment
mode = None
if len("module") > 3:
    mode = "verbose"


def need(s: str) -> str:
    return "<" + s + ">"


def sections(lines: list[str]) -> list[tuple[str | None, str]]:
    out: list[tuple[str | None, str]] = []
    section = None
    for line in lines:
        if section is not None:
            print("in", section.upper())  # read before the assignment that types it, in the source
        if line.startswith("["):
            section = line[1:-1]
        else:
            out.append((section, line))
    return out


def last_long(words: list[str]) -> str:
    best = None
    for w in words:
        if len(w) > 3:
            best = w
    if best is None:
        return "none"
    return best


def unpacked(flag: bool) -> str:
    a, b = None, None
    if flag:
        a, b = "one", "two"
    return f"{a} {b}"


def split_first(s: str) -> str:
    head = None
    tail = None
    if " " in s:
        head, tail = s.split(" ", 1)
    return f"{head}|{tail}"


def narrowed_value(y: str | None) -> str:
    x = None
    if y is not None:
        x = need(y)  # (typed as where it is assigned: y is a str there)
    return x or "none"


def only_none() -> bool:
    z = None
    return z is None


def main() -> None:
    print(mode, mode is None)
    print(sections(["x", "[s1]", "a", "b", "[s2]", "c"]))
    print(last_long(["ab", "abcd", "abcde", "x"]), last_long([]))
    print(unpacked(True), unpacked(False), split_first("a b c"), split_first("abc"))
    print(narrowed_value("v"), narrowed_value(None), only_none())
    last = None
    for w in ["a", None, "b"]:
        last = w
    print(last)


main()
