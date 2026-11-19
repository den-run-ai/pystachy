# An enum class's __new__, in the form CPython's enum documentation gives one, makes each member
# of the items of its value: it makes the member with its data type's __new__ (object's; int's
# in an IntEnum, str's in a StrEnum), may assign its _value_ and attributes, and returns it. The
# compiler computes the _value_ it gives each member (which the member's value as written may
# differ from), and the rest of its body runs for each member, an alias too, in body order.
import enum
from enum import Enum, IntEnum, StrEnum


class Kind(IntEnum):
    # (inspect's _ParameterKind: the value is the number of names before, the item a description)
    POSITIONAL_ONLY = 'positional-only'
    POSITIONAL_OR_KEYWORD = 'positional or keyword'
    VAR_POSITIONAL = 'variadic positional'

    def __new__(cls, description):
        value = len(cls.__members__)
        member = int.__new__(cls, value)
        member._value_ = value
        member.description = description
        return member

    def __str__(self) -> str:
        return self.name


class Status(IntEnum):
    # (http's HTTPStatus: the value is the first item, the others are attributes; one has a default)
    def __new__(cls, value, phrase, description=''):
        obj = int.__new__(cls, value)
        obj._value_ = value
        obj.phrase = phrase
        obj.description = description
        return obj

    @property
    def is_success(self) -> bool:
        return 200 <= self <= 299

    CONTINUE = 100, 'Continue', 'Request received, please continue'
    OK = 200, 'OK', 'Request fulfilled, document follows'
    EARLY_HINTS = 103, 'Early Hints'
    NOT_FOUND = (404, 'Not Found', 'Nothing matches the given URI')
    FINE = 200, 'Fine', 'An alias of OK'
    MISSING = NOT_FOUND


class Method(StrEnum):
    def __new__(cls, value, description):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.description = description
        return obj

    GET = 'GET', 'Retrieve the target.'
    POST = 'POST', 'Perform target-specific processing.'


class Planet(Enum):
    # (no _value_ assigned: the value as written is the member's value)
    def __new__(cls, mass, radius):
        obj = object.__new__(cls)
        obj.mass = mass
        obj.radius = radius
        obj.order = len(cls.__members__)
        print("new planet", mass)
        return obj

    MERCURY = (3.303e+23, 2.4397e6)
    EARTH = (5.976e+24, 6.37814e6)
    TERRA = (5.976e+24, 6.37814e6)

    def gravity(self) -> float:
        return 6.67300E-11 * self.mass / (self.radius * self.radius)


class AutoNumber(Enum):
    # (the documentation's recipe: an enum class without members, whose __new__ the classes
    # deriving from it make their members with)
    def __new__(cls):
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


class Color(AutoNumber):
    RED = ()
    GREEN = ()
    BLUE = ()


class Swatch(AutoNumber):
    DARK = ()
    LIGHT = ()


class Scaled(enum.Enum):
    def __new__(cls, base, shift=1):
        obj = object.__new__(cls)
        code = base * 10 + shift
        obj._value_ = code
        obj.base = base
        return obj

    A = 1
    B = 2, 5
    C = (A + 2, 0)


for k in Kind:
    print(k, repr(k), k.value, k.description, k + 1, k == k.value, k.name)
print(Kind(1), Kind["VAR_POSITIONAL"].description, Kind.POSITIONAL_ONLY < Kind.VAR_POSITIONAL, len(Kind))
for s in Status:
    print(s, repr(s), s.value, s.phrase, s.description == '', s.is_success, s + 0)
print(Status(200).phrase, Status["NOT_FOUND"].value, Status.OK == 200, Status.FINE is Status.OK, Status.FINE.phrase)
print(list(Status.__members__), f"{Status.OK}", str(Status.NOT_FOUND), Status(103).description, Status.MISSING is Status.NOT_FOUND)
for m in Method:
    print(m, repr(m), m.value, m.description, m == "GET", m.lower())
print(Method("POST").description, f"{Method.GET}", Method.GET + "!", len(Method.POST))
for p in Planet:
    print(p, p.value, p.order, round(p.gravity(), 2))
print(Planet.TERRA is Planet.EARTH, Planet((3.303e+23, 2.4397e6)), Planet["TERRA"].order)
print(list(Color), Color.GREEN.value, Color(3), Color["RED"], list(Swatch), Swatch.LIGHT.value)
print(list(Scaled), Scaled.B.base, Scaled(25), Scaled.C.value, Scaled.A.value)
try:
    Status(999)
except ValueError as e:
    print("ValueError:", e)
