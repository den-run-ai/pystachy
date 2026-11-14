# error: dict keys must be int or str, objects, or tuples of int, bool, str, str | None and objects, not A | B (a union's classes must hash and compare by identity: none may define __hash__ or __eq__)
class A:
    def __eq__(self, other: object) -> bool:
        return True

    def __hash__(self) -> int:
        return 1


class B:
    pass


d: dict[A | B, int] = {}
d[A()] = 1
print(len(d))
