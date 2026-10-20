# Valid patterns close to CPython's errors in them. A function that is never called holds them, so
# Pystachy, which does not compile match statements, accepts the program as CPython runs it.
class P:
    def __init__(self) -> None:
        self.a = 0


def never(x, k):
    match x, k:
        case 0 | 1.5 | -2 | 3j | -4j | 1 + 2j | -1.5 - 0j | "a" "b" | b"c" | None | True | False:
            pass
        case P.a | k.real.imag | (P.a):
            pass
        case [a, *rest] | (a, *rest) if a:
            pass
        case [] | () | {} | [*_] | (*_,) | [_, *_, _]:
            pass
        case {0: a, "0": b, b"0": c, 0.5: d, 1j: e, None: f, P.a: g, P.a: h, **rest}:
            pass
        case {0x10000000000000000: a, 0x20000000000000000: b, 1e20: c, 1e21: d, -0.0: e, 1: f}:
            pass
        case {100000000000000000000: a, 100000000000000000001: b, 2.5: c, 2.5j: d, 1 + 2.5j: e}:
            pass
        case y if y:
            pass
        case ([y] as z) | ([z] as y):
            pass
        case [match, case, type, _] | {"m": match, "c": case, "t": type}:
            pass
        case P(1, [2, *c], a=3, b=[*d],) | P(c, d):
            pass
        case [
            1,
            2,
        ] as match:
            pass
        case [[[[x2]]], y2] | {"k": [x2, *y2]} | {"j": (y2, *x2)}:
            pass
        case ((1 | 2) as w) | (3 as w):
            pass
        case _ if k:
            pass
        case _:
            pass


print("ran")
