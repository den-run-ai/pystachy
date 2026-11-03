# Pystachy's subset implementation of CPython 3.13.16's Lib/enum.py (lib/compatibility.md#enum).
# CPython makes an enum class with its metaclass, EnumType, whose __prepare__, __new__ and
# __call__ have no form in a compiled program: here the compiler makes it from the class statement
# of a class that derives from Enum, IntEnum or StrEnum (Loader's enum_classes). Each member is a
# class attribute, an object of the class that holds its _name_ and _value_ (a field of the type
# of the members' values), and the class as a value (iteration, len(), in, C(value), C[name],
# __members__, repr()) is an object of EnumType that the module makes after the class statement.
# The methods below are CPython's for the members (repr(), str(), format(), hash(), copies), with
# the operations IntEnum and StrEnum members take from int and str.
from types import MappingProxyType

__all__ = [
        'EnumType', 'EnumMeta',
        'Enum', 'IntEnum', 'StrEnum', 'ReprEnum',
        'auto', 'unique',
        ]


class EnumType:
    """
    Metaclass for Enum
    """
    # (here the class of an enum class as a value: the compiler makes one object of it for each
    # enum class, with the class's name, its members in definition order and its members by name,
    # aliases included)

    def __init__(self, name, members, member_map):
        self._cls_name_ = name
        self._member_list_ = members
        self._member_map_ = member_map

    def __bool__(self) -> bool:
        """
        classes/types should always be True.
        """
        return True

    def __call__(self, value):
        """
        Either returns an existing member, or creates a new enum class.
        """
        # (Enum.__new__'s lookup by value: a member is its own, and another value finds the
        # member whose value equals it; making a new enum class is not supported)
        members = self._member_list_
        if __pys_enum_is(value, members):
            return value
        for member in members:
            if member._value_ == value:
                return member
        raise ValueError("%r is not a valid %s" % (value, self._cls_name_))

    def __contains__(self, value) -> bool:
        """Return True if `value` is in `cls`.

        `value` is in `cls` if:
        1) `value` is a member of `cls`, or
        2) `value` is the value of one of the `cls`'s members.
        """
        members = self._member_list_
        if __pys_enum_is(value, members):
            return True
        for member in members:
            if member._value_ == value:
                return True
        return False

    def __getitem__(self, name: str):
        """
        Return the member matching `name`.
        """
        return self._member_map_[name]

    def __iter__(self):
        """
        Return members in definition order.
        """
        return iter(self._member_list_)

    def __len__(self) -> int:
        """
        Return the number of members (no aliases)
        """
        return len(self._member_list_)

    def _members_view_(self):
        """
        Returns a mapping of member name->value.

        This mapping lists all enum members, including aliases.  Note that
        this is a read-only view of the internal mapping.
        """
        # (CPython's __members__ property: C.__members__ calls it)
        return MappingProxyType(self._member_map_)

    def __repr__(self) -> str:
        return "<enum %r>" % self._cls_name_


EnumMeta = EnumType


class auto:
    """
    Instances are replaced with an appropriate value in Enum class suites.
    """
    # (the compiler gives each auto() in an enum class body its member's value, as CPython's
    # _generate_next_value_ does)

    def __repr__(self) -> str:
        return "auto(_auto_null)"


class Enum:
    """
    Create a collection of name/value pairs.

    Example enumeration:

    >>> class Color(Enum):
    ...     RED = 1
    ...     BLUE = 2
    ...     GREEN = 3

    Access them by:

    - attribute access:

      >>> Color.RED
      <Color.RED: 1>

    - value lookup:

      >>> Color(1)
      <Color.RED: 1>

    - name lookup:

      >>> Color['RED']
      <Color.RED: 1>

    Enumerations can be iterated over, and know how many members they have:

    >>> len(Color)
    3

    >>> list(Color)
    [<Color.RED: 1>, <Color.BLUE: 2>, <Color.GREEN: 3>]

    Methods can be added to enumerations, and members can have their own
    attributes -- see the documentation for details.
    """
    _name_: str

    def __repr__(self) -> str:
        return "<%s.%s: %s>" % (self.__class__.__name__, self._name_, self._value_repr_())

    def __str__(self) -> str:
        return "%s.%s" % (self.__class__.__name__, self._name_, )

    def __format__(self, format_spec: str) -> str:
        return format(str(self), format_spec)

    def __hash__(self) -> int:
        return hash(self._name_)

    def __deepcopy__(self, memo):
        return self

    def __copy__(self):
        return self

    @property
    def name(self) -> str:
        """The name of the Enum member."""
        return self._name_

    def _value_repr_(self) -> str:
        # (repr() of the member's value: each enum class's, which the compiler makes)
        return ""


class ReprEnum(Enum):
    """
    Only changes the repr(), leaving str() and format() to the mixed-in type.
    """


def _int_of(x, a, op: str):
    # operand x of IntEnum member a's operation op, as int's operation takes it: x, a number, or
    # an IntEnum member's value; else CPython's TypeError, once int's method and x's decline
    if isinstance(x, int) or isinstance(x, float):
        return x
    if isinstance(x, IntEnum):
        return x._value_
    if op in "< <= > >=":
        raise TypeError("'%s' not supported between instances of '%s' and '%s'" % (op, type(a).__name__, type(x).__name__))
    raise TypeError("unsupported operand type(s) for %s: '%s' and '%s'" % (op, type(a).__name__, type(x).__name__))


class IntEnum(ReprEnum):
    """
    Enum where members are also (and must be) ints
    """
    # (a member is an object of its class, which has int's operations below; it is no int where
    # an int is typed)
    _value_: int

    @property
    def value(self) -> int:
        """The value of the Enum member."""
        return self._value_

    def _value_repr_(self) -> str:
        return repr(self._value_)

    def __str__(self) -> str:
        return repr(self._value_)

    def __format__(self, format_spec: str) -> str:
        return format(self._value_, format_spec)

    def __hash__(self) -> int:
        return hash(self._value_)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, IntEnum):
            return self._value_ == other._value_
        if isinstance(other, int) or isinstance(other, float):
            return self._value_ == other
        return False

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __lt__(self, other):
        return self._value_ < _int_of(other, self, '<')

    def __le__(self, other):
        return self._value_ <= _int_of(other, self, '<=')

    def __gt__(self, other):
        return self._value_ > _int_of(other, self, '>')

    def __ge__(self, other):
        return self._value_ >= _int_of(other, self, '>=')

    def __add__(self, other):
        return self._value_ + _int_of(other, self, '+')

    def __sub__(self, other):
        return self._value_ - _int_of(other, self, '-')

    def __mul__(self, other):
        return self._value_ * _int_of(other, self, '*')

    def __truediv__(self, other):
        return self._value_ / _int_of(other, self, '/')

    def __floordiv__(self, other):
        return self._value_ // _int_of(other, self, '//')

    def __mod__(self, other):
        return self._value_ % _int_of(other, self, '%')

    def __and__(self, other):
        return self._value_ & _int_of(other, self, '&')

    def __or__(self, other):
        return self._value_ | _int_of(other, self, '|')

    def __xor__(self, other):
        return self._value_ ^ _int_of(other, self, '^')

    def __lshift__(self, other):
        return self._value_ << _int_of(other, self, '<<')

    def __rshift__(self, other):
        return self._value_ >> _int_of(other, self, '>>')

    def __neg__(self) -> int:
        return -self._value_

    def __pos__(self) -> int:
        return self._value_

    def __abs__(self) -> int:
        return abs(self._value_)

    def __invert__(self) -> int:
        return ~self._value_

    def __bool__(self) -> bool:
        return self._value_ != 0

    def __int__(self) -> int:
        return self._value_

    def __index__(self) -> int:
        return self._value_

    def __float__(self) -> float:
        return float(self._value_)


def _str_of(x, a, op: str):
    # operand x of StrEnum member a's operation op, as str's operation takes it: x, a str, or a
    # StrEnum member's value; else CPython's TypeError, once str's method and x's decline
    if isinstance(x, str):
        return x
    if isinstance(x, StrEnum):
        return x._value_
    if op == "+":
        raise TypeError('can only concatenate str (not "%s") to str' % type(x).__name__)
    if op == "in":
        raise TypeError("'in <string>' requires string as left operand, not %s" % type(x).__name__)
    raise TypeError("'%s' not supported between instances of '%s' and '%s'" % (op, type(a).__name__, type(x).__name__))


class StrEnum(ReprEnum):
    """
    Enum where members are also (and must be) strings
    """
    # (a member is an object of its class, which has the str operations below; it is no str where
    # a str is typed)
    _value_: str

    @property
    def value(self) -> str:
        """The value of the Enum member."""
        return self._value_

    def _value_repr_(self) -> str:
        return repr(self._value_)

    def __str__(self) -> str:
        return self._value_

    def __format__(self, format_spec: str) -> str:
        return format(self._value_, format_spec)

    def __hash__(self) -> int:
        return hash(self._value_)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, StrEnum):
            return self._value_ == other._value_
        if isinstance(other, str):
            return self._value_ == other
        return False

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __lt__(self, other):
        return self._value_ < _str_of(other, self, '<')

    def __le__(self, other):
        return self._value_ <= _str_of(other, self, '<=')

    def __gt__(self, other):
        return self._value_ > _str_of(other, self, '>')

    def __ge__(self, other):
        return self._value_ >= _str_of(other, self, '>=')

    def __add__(self, other):
        return self._value_ + _str_of(other, self, '+')

    def __len__(self) -> int:
        return len(self._value_)

    def __contains__(self, sub) -> bool:
        return _str_of(sub, self, "in") in self._value_

    def __bool__(self) -> bool:
        return self._value_ != ""

    def upper(self) -> str:
        return self._value_.upper()

    def lower(self) -> str:
        return self._value_.lower()

    def startswith(self, prefix) -> bool:
        return self._value_.startswith(prefix)

    def endswith(self, suffix) -> bool:
        return self._value_.endswith(suffix)

    def encode(self, encoding: str = "utf-8", errors: str = "strict") -> bytes:
        return self._value_.encode(encoding, errors)


def unique(enumeration):
    """
    Class decorator for enumerations ensuring unique member values.
    """
    # (the compiler checks the members of an enum class that @unique decorates, and reports its
    # aliases as an error: CPython's ValueError where the class statement runs)
    return enumeration
