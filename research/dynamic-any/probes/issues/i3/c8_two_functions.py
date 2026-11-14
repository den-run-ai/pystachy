# pystachy: dynamic-any

def esc_a(s: str) -> str:
    return s.upper()


def esc_b(s: str) -> str:
    return s.lower()


def pick(multi: bool, s: str) -> str:
    if multi:
        f = esc_a
    else:
        f = esc_b
    return f(s)


print(pick(True, "Ab"), pick(False, "Ab"))
