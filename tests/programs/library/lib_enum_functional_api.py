# CPython's functional API at the top of a module: NAME = Enum("NAME", names) is the class that
# EnumType._create_ makes, of names as a str (split at commas and spaces), a list or tuple of
# names (valued from start=: Enum's count up, a flag's are powers of two, StrEnum's are the names
# in lower case), (name, value) pairs or a dict, with type=int, boundary= and module=__name__.
from enum import CONFORM, Enum, Flag, IntEnum, IntFlag, StrEnum

Animal = Enum("Animal", "ANT BEE CAT DOG")
Color = Enum("Color", "RED, GREEN, BLUE", start=0)
Shape = Enum("Shape", [("SQUARE", 4), ("TRIANGLE", 3), ("BOX", 4)])
Mode = Enum("Mode", {"read": "r", "write": "w"}, module=__name__)
Level = IntEnum("Level", ("LOW", "HIGH"), start=10)
Perm = Flag("Perm", "R W X")
Bits = IntFlag("Bits", ["A", "B"], boundary=CONFORM)
Word = StrEnum("Word", "Alpha Beta")
Code = Enum("Code", "OK FAIL", type=int)

print(list(Animal), Animal.CAT.value, Animal(2))
print(list(Color), Color.RED.value, list(Shape), Shape.BOX is Shape.SQUARE)
print(list(Mode), Mode("w"), list(Level), Level.HIGH + 1)
print(list(Perm), Perm.R | Perm.X, list(Bits), repr(Bits(7)))
print(list(Word), Word.Alpha.value, Code.FAIL + 1, repr(Code.OK))
print(Animal.__name__, repr(Perm), Animal.CAT.name)
