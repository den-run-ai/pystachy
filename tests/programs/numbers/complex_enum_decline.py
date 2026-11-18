from enum import IntEnum, IntFlag


class Number(IntEnum):
    ONE = 1
    TWO = 2

    def __eq__(self, other) -> bool:
        print("enum eq", self.value)
        return NotImplemented

    def __ne__(self, other) -> bool:
        print("enum ne", self.value)
        return NotImplemented


class Flag(IntFlag):
    A = 1

    def __eq__(self, other) -> bool:
        print("flag eq")
        return NotImplemented


def compare(z: complex, member: Number) -> None:
    print(member == z, z == member, member != z, z != member)
    print(member in (z,), z in (member,), (member, member).count(z))


compare(1 + 0j, Number.ONE)
compare(1 + 0j, Number.TWO)
compare(1j, Number.ONE)
compare(None, Number.ONE)
compare(1 + 0j, None)
compare(None, None)
print(Flag.A == 1 + 0j, 1 + 0j == Flag.A, Flag.A != 1 + 0j, 1 + 0j != Flag.A)
