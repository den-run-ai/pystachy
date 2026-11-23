import re
import typing as t
from typing import Match as TextMatch, Pattern as TextPattern


def compile_word(s: str) -> TextPattern[str]:
    return re.compile(s)


def search(pattern: "t.Pattern[str]", s: str) -> t.Match[str] | None:
    return pattern.search(s)


def span(match: TextMatch[str]) -> tuple[int, int]:
    return match.span()


found = search(compile_word(r"\w+"), "--word")
if found is not None:
    print(span(found), found.group(0))
print(search(compile_word(r"\d+"), "abc"))
