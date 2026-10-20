# Objects as dict keys (#484) in a dict comprehension (#472), a | b and dict() of pairs (#478), ** dict
# displays (#479) and popitem() (#470): their __hash__ and __eq__ calls, in CPython's order.
log: list[str] = []


class K:
    def __init__(self, v: int) -> None:
        self.v = v

    def __hash__(self) -> int:
        log.append(f"h{self.v}")
        return self.v % 2

    def __eq__(self, other: "K") -> bool:
        log.append(f"e{self.v}{other.v}")
        return self.v == other.v

    def __repr__(self) -> str:
        return f"K({self.v})"


def main() -> None:
    a = {K(i): i for i in range(3)}
    print(a, log)
    log.clear()
    b = {K(1): 10, K(5): 50}
    u = a | b
    print(u, log)
    log.clear()
    m = {**a, **b, K(7): 70}
    print(m, log)
    log.clear()
    p = dict([(K(2), 2), (K(4), 4), (K(2), 22)])
    print(p, log)
    log.clear()
    z = {K(0): 0, K(2): 2, K(4): 4}
    print(z.popitem(), z.popitem(), z, log)
    z[K(6)] = 6
    print(z, z.popitem(), z.popitem(), z)


main()
