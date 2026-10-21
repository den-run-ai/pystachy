# re.Pattern[str] and re.Match[str] annotate the patterns and matches lib/re makes, evaluated or
# quoted, as CPython's _sre types are generic (their __class_getitem__)
import re
from typing import Callable

WORD: re.Pattern[str] = re.compile(r"(?P<word>\w+)")


def first(m: re.Match[str]) -> str:
    g = m.group(0)
    return g if g is not None else ""


def upper(m: re.Match[str]) -> str:
    return first(m).upper()


def words(p: re.Pattern[str], s: str) -> list[str]:
    return [first(m) for m in p.finditer(s)]


def find(p: "re.Pattern[str]", s: str) -> "re.Match[str] | None":
    return p.search(s)


print(words(WORD, "ab cd ef"), WORD.sub(upper, "ab cd"))
m = find(WORD, "  hello")
if m is not None:
    print(m.span(), m.group("word"), first(m))
print(find(re.compile(r"\d"), "abc"))
handler: Callable[[re.Match[str]], str] = upper
print(re.sub(r"[a-z]+", handler, "x1yz2"))
