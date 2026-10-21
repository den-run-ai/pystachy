# Dataclasses (#483) as dict keys and set elements (#484): frozen=True (with eq) and
# unsafe_hash=True write a __hash__ of the fields that hash (field(hash=False) and compare=False
# leave one out), eq=False hashes by identity, and a plain eq=True dataclass is unhashable.
from dataclasses import dataclass, field


@dataclass(frozen=True)
class F:
    x: int
    y: str = "a"


@dataclass(eq=False)
class I:
    x: int


@dataclass(unsafe_hash=True)
class U:
    x: int
    tags: list[int] = field(default_factory=list, hash=False, compare=False)


@dataclass(frozen=True)
class G(F):
    z: int = 0


def main() -> None:
    d = {F(1): "one", F(1, "b"): "oneb"}
    print(d[F(1)], F(1, "b") in d, len({F(2), F(2), G(2)}), hash(F(3)) == hash(F(3)))
    i1 = I(1)
    e = {i1: 1, I(1): 2}
    print(len(e), e[i1])
    u = {U(1): "u"}
    print(u[U(1, [5])])
    g = {G(1, "a", 2): 1}
    print(G(1, "a", 2) in g, G(1, "a", 3) in g)


main()


@dataclass
class P:
    x: int


try:
    d = {P(1): 1}
    print(d)
except TypeError as e:
    print("TypeError", e)
