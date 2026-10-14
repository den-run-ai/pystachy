import re

def show(pattern: str, text: str, default: str | None = None) -> None:
    match = re.fullmatch(pattern, text)
    assert match is not None
    values: tuple[str | None, ...] = match.groups(default)
    print("groups", pattern, default, len(values), values, repr(values))
    print("equal", values == match.groups(default=default), values != match.groups(default))
    print("changed-default", values == match.groups("different"), values != match.groups("different"))
    for value in values:
        print("member", repr(value))
    for index in range(-len(values), len(values)):
        print("index", index, repr(values[index]))
    indices: list[int] = [len(values), -len(values) - 1]
    for index in indices:
        try:
            print(values[index])
        except IndexError as error:
            print("bounds", index, str(error))

show("a", "a")
show("(a)", "a")
show("(a)(b)?", "a")
show("(a)(b)?(c)", "ac")
show("(a)(b)?(c)?(d)", "ad")
show("(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)", "abcdefghij")
show("(a)(b)?", "a", "missing")
show("(a)(b)?(c)", "ac", "")
show("(?P<first>a)(?P<optional>b)?(?P<last>c)", "ac", "fallback")
