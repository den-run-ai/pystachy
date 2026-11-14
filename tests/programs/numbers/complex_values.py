# complex numbers as values: module constants, defaults, parameters and returns, fields, dataclass
# fields, sorting keys, comprehensions, dict keys and sets (__hash__, __eq__), identity and copies
import copy
from dataclasses import dataclass

ROOT = 1j
SCALE: complex = 2 + 0j


def rotate(z: complex, turns: int = 1) -> complex:
    for _ in range(turns):
        z = z * ROOT
    return z


def mean(zs: list[complex]) -> complex:
    total = 0j
    for z in zs:
        total += z
    return total / len(zs)


class Phasor:
    def __init__(self, z: complex) -> None:
        self.z = z
        self.history = [z]

    def step(self, w: complex = 1 + 1j) -> None:
        self.z = self.z * w
        self.history.append(self.z)


@dataclass
class Point:
    at: complex
    label: str


p = Phasor(1 + 0j)
p.step()
p.step(SCALE)
print(p.z, p.history, rotate(1 + 2j, 3), mean([1j, 2 + 0j, 3.5 - 1j]))
pt = Point(3 - 4j, "a")
print(pt, pt.at.real, abs(pt.at))
zs = [3 + 4j, 1j, -2.5 + 0j, 0j]
print(sorted(zs, key=abs), max(zs, key=lambda z: z.imag), [z.conjugate() for z in zs if z])
print({z: abs(z) for z in zs}, set([1j, 1j, 2j]) == {2j, 1j}, (1j, 2) == (1j, 2), [1j] != [1j])
print(type(ROOT) is complex, type(ROOT) == complex, complex.__name__, isinstance(ROOT, (int, complex)))
print(copy.copy(ROOT) is ROOT, copy.deepcopy([ROOT]), complex(ROOT) is ROOT, +ROOT is ROOT)
print(ROOT == None, ROOT != "1j", ROOT in [2j, 1j], [1j, 2j].index(2j), [1j, 2j, 1j].count(1j))
w: complex | None = None
if w is None:
    w = 5j
print(w * 2, str(w), len(str(w)))
print(1j * 1j, (1 + 1j) ** 2, 1 / (1 + 1j), -(1 - 1j), abs(-3j), True + 1j, 2.5 * 1j)
