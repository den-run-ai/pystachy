# Generated matchers may run out of source-call depth before their local depth
# cap. Both entry paths must restart the interpreter with the original state,
# even after capture marks were written. The .path selects the existing matchers.
import re
import sys


def show(match: re.Match | None) -> None:
    if match is None:
        print(None)
    else:
        print(match.span(), [match.span(i) for i in range(1, match.re.groups + 1)], match.lastindex)


def exercise(pattern: str, text: str, depth: int) -> None:
    if depth:
        exercise(pattern, text, depth - 1)
        return
    compiled = re.compile(pattern)
    show(compiled.match(text))
    show(compiled.search("!!" + text))


def replacement(match: re.Match) -> str:
    raise RecursionError("replacement sentinel")


def callback(depth: int) -> None:
    if depth:
        callback(depth - 1)
        return
    try:
        re.sub(r"(?:ab)*c", replacement, "ab" * 600 + "c")
    except RecursionError as error:
        print(str(error))
    else:
        print("missing callback error")


cases: list[tuple[str, str]] = [
    (r"(?:ab)*c", "ab" * 600 + "c"),
    (r"((a)|b)+", "ab" * 600),
    (r"(a|b)*?c", "ab" * 600 + "c"),
]
# Populate the pattern cache before lowering the limit: the limit is testing
# matching and fallback, independently of pattern compilation's own call depth.
for pattern, text in cases:
    re.compile(pattern)
original = sys.getrecursionlimit()
for limit in [1000, 80]:
    sys.setrecursionlimit(limit)
    for depth in [0, 12]:
        print(limit, depth)
        for pattern, text in cases:
            exercise(pattern, text, depth)
        callback(depth)
sys.setrecursionlimit(original)
