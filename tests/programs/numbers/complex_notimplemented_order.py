# A declined foreign comparison is called once, in both operand orders, also
# through runtime subclasses and tuple searches. None never exposes a payload.
class Plain:
    def __eq__(self, other) -> bool:
        print("plain eq")
        return NotImplemented

    def __ne__(self, other) -> bool:
        print("plain ne")
        return NotImplemented


class Base:
    def __eq__(self, other) -> bool:
        print("base eq")
        return NotImplemented


class Child(Base):
    def __eq__(self, other) -> bool:
        print("child eq")
        return NotImplemented


def plain(z: complex, other: Plain) -> None:
    print(z == other, other == z, z != other, other != z)
    print(other in (z,), z in (other,), (z, z).count(other))


def runtime(z: complex, other: Base) -> None:
    print(z == other, other == z, z != other, other != z)
    print(other in (z,), z in (other,), (z, z).count(other))


plain(1j, Plain())
plain(None, Plain())
plain(1j, None)
plain(None, None)
runtime(1j, Base())
runtime(1j, Child())
runtime(None, Child())
runtime(1j, None)
runtime(None, None)
print(complex(1, 0).__eq__(1), complex(1, 0).__eq__(2.0), complex(1, 0).__eq__(True))
