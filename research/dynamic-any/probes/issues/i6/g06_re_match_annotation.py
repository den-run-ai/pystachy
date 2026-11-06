import re


def first(m: re.Match[str]) -> str:
    return m.group(0)


m = re.match(r"\w+", "ab cd")
if m:
    print(first(m))
