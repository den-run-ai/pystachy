"""The matchers that lib/re runs in place of its interpreter for a program's own patterns: none here.

tools/re_specialize.py writes a module of this name with a matcher for each pattern a program uses
often (from a profile of a CPython run). Put it next to the program or on PYSTACHY_PATH, where
imports find it before this one; re's Pattern looks its pattern up there (lookup()) and runs the
matcher on the subjects it reads in place: for match() and fullmatch() (match()), and at each
position a search tries (attempt()). This module has no matchers, so every pattern runs on
lib/re/_sre.py's interpreter, as before.
"""

# (pattern, flags) -> its matcher; and the code each was generated from, which lookup() checks
_KEYS: dict[tuple[str, int], int] = {}
_CODES: list[list[int]] = []


def lookup(pattern: str, flags: int, code: list[int]) -> int:
    # the matcher of the pattern compiled with flags to code, or -1
    key = (pattern, flags)
    if key in _KEYS:
        i = _KEYS[key]
        if _CODES[i] == code:
            return i
    return -1


def match(i: int, state) -> int:
    # sre_match() from state.ptr by matcher i: 1 or 0, or -1 where it declines (the interpreter then runs)
    return -1


def attempt(i: int, state, toplevel: bool) -> int:
    # sre_match() of the whole code at state.start by matcher i: 1 or 0, or -1 where it declines
    return -1
