# A bounded match (patterns.py) binds a case's captures with := in the test of the if statement
# each case becomes: the values an alternative stages, then the names, then the guard. Definite
# assignment (flow.py) knows that such a name is bound where the test is true, and in the and's
# operands after the one that bound it: the case bodies, the guards and the commits of an
# or-pattern's staged values read them without an is-assigned flag, whose UnboundLocalError
# would call pys_raise. match_captures_bound.calls pins that none of these functions raises.


def pick(t: tuple[int, int]) -> int:
    match t:
        case (0, v) | (v, 0) if v > 0:
            return v
        case (a, b) if a < b:
            return b
    return -1


def word(t: tuple[str, str]) -> str:
    match t:
        case (w, "") | ("", w) if len(w) > 0:
            return w
        case (w, _):
            return w
    return ""


def walrus(a: int, b: int) -> int:
    if a > 0 and (c := b) > 0:
        return c
    return 0


print(pick((0, 5)), word(("a", "")), walrus(1, 2))
