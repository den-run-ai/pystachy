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
        'Enum', 'IntEnum', 'StrEnum', 'Flag', 'IntFlag', 'ReprEnum',
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
        # member whose value equals it; making a new enum class is not supported). A member is
        # found by its class, also where value's type is a base class's (x: Enum) or Any
        members = self._member_list_
        own = __pys_enum_own(value, members)
        if own is not None:
            return own
        for member in members:
            if member._value_ == value:
                return member
        # (the class's _missing_(value), where it defines one: a member, or None for the
        # ValueError; CPython's TypeError for another result is a compile-time error here)
        hit = __pys_enum_missing(members, value)
        if hit is not None:
            return hit
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
    if isinstance(x, IntEnum) or isinstance(x, IntFlag):
        return x._value_
    if op in "< <= > >=":
        raise TypeError("'%s' not supported between instances of '%s' and '%s'" % (op, type(a).__name__, type(x).__name__))
    raise TypeError("unsupported operand type(s) for %s: '%s' and '%s'" % (op, type(a).__name__, type(x).__name__))


def _int_left(x, a, op: str):
    # left operand x of IntEnum member a's reflected operation op (x op a), as int's reflected
    # operation takes it: x, a number; else CPython's TypeError, which names x's type first
    if isinstance(x, int) or isinstance(x, float):
        return x
    if isinstance(x, IntEnum) or isinstance(x, IntFlag):
        return x._value_
    raise TypeError("unsupported operand type(s) for %s: '%s' and '%s'" % (op, type(x).__name__, type(a).__name__))


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
        # (int's and str's __format__: with an empty spec, str() of the object, which a class's
        # own __str__ makes)
        if format_spec == "":
            return str(self)
        return format(self._value_, format_spec)

    def __hash__(self) -> int:
        return hash(self._value_)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, IntEnum) or isinstance(other, IntFlag):
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

    def __radd__(self, other):
        return _int_left(other, self, '+') + self._value_

    def __rsub__(self, other):
        return _int_left(other, self, '-') - self._value_

    def __rmul__(self, other):
        return _int_left(other, self, '*') * self._value_

    def __rtruediv__(self, other):
        return _int_left(other, self, '/') / self._value_

    def __rfloordiv__(self, other):
        return _int_left(other, self, '//') // self._value_

    def __rmod__(self, other):
        return _int_left(other, self, '%') % self._value_

    def __rlshift__(self, other):
        return _int_left(other, self, '<<') << self._value_

    def __rrshift__(self, other):
        return _int_left(other, self, '>>') >> self._value_

    def __rand__(self, other):
        return _int_left(other, self, '&') & self._value_

    def __ror__(self, other):
        return _int_left(other, self, '|') | self._value_

    def __rxor__(self, other):
        return _int_left(other, self, '^') ^ self._value_

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
        # (int's and str's __format__: with an empty spec, str() of the object, which a class's
        # own __str__ makes)
        if format_spec == "":
            return str(self)
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


class _IntMixin(IntEnum):
    # (an enum class of int and Enum, class C(int, Enum), which the compiler makes as one derived
    # from this class: an IntEnum member's operations, with Enum's str() and format(), as CPython
    # 3.12 gives a mixed-in enum class; isinstance() of a member and IntEnum or ReprEnum, which
    # CPython's answers False, is a compile-time error)

    def __str__(self) -> str:
        return "%s.%s" % (self.__class__.__name__, self._name_, )

    def __format__(self, format_spec: str) -> str:
        return format(str(self), format_spec)


class _StrMixin(StrEnum):
    # (an enum class of str and Enum, class C(str, Enum): a StrEnum member's operations, with
    # Enum's str() and format(), as for _IntMixin)

    def __str__(self) -> str:
        return "%s.%s" % (self.__class__.__name__, self._name_, )

    def __format__(self, format_spec: str) -> str:
        return format(str(self), format_spec)


def _bits(num: int) -> int:
    # num.bit_length()
    if num < 0:
        num = -(num + 1) if num != -9223372036854775807 - 1 else 9223372036854775807
        if num == 9223372036854775807:
            return 64
        num += 1
    n = 0
    while num:
        num >>= 1
        n += 1
    return n


def _bit_count(num: int) -> int:
    # num.bit_count() of num >= 0
    n = 0
    while num:
        num &= num - 1
        n += 1
    return n


def _flag_bin(num: int, max_bits: int | None = None) -> str:
    """
    Like built-in bin(), except negative values are represented in
    twos-complement, and the leading bit always indicates sign
    (0=positive, 1=negative).

    >>> bin(10)
    '0b0 1010'
    >>> bin(~10)   # ~10 is -11
    '0b1 0101'
    """
    # (CPython's enum.bin(), which the module's name bin would hide the builtin for here)
    k = _bits(num)
    sign = "0b0" if num >= 0 else "0b1"
    # Reading the low k bits directly also works for negative values.
    digits = ""
    for i in range(k - 1, -1, -1):
        digits += "1" if (num >> i) & 1 else "0"
    if max_bits is not None:
        if len(digits) < max_bits:
            digits = (sign[-1] * max_bits + digits)[-max_bits:]
    return "%s %s" % (sign, digits)


class _FlagType:
    """
    Metaclass for Enum
    """
    # (EnumType for a Flag or IntFlag class: the compiler makes one object of it for each flag
    # class, with its name, its canonical members (single-bit) in definition order, its members by
    # name, aliases included, its members by value, which the pseudo-members join as they are made,
    # and CPython's _flag_mask_, _singles_mask_, _all_bits_ and boundary, STRICT for Flag and KEEP
    # for IntFlag)

    def __init__(self, name, members, member_map, value_map, flag_mask: int, singles_mask: int, all_bits: int, keep: bool):
        self._cls_name_ = name
        self._member_list_ = members
        self._member_map_ = member_map
        self._value2member_map_ = value_map
        self._flag_mask_ = flag_mask
        self._singles_mask_ = singles_mask
        self._all_bits_ = all_bits
        self._keep_ = keep

    def __bool__(self) -> bool:
        """
        classes/types should always be True.
        """
        return True

    def __call__(self, value):
        """
        Either returns an existing member, or creates a new enum class.
        """
        # (Enum.__new__'s lookup by value, then Flag._missing_'s pseudo-member)
        members = self._member_list_
        own = __pys_enum_own(value, members)
        if own is not None:
            return own
        if not isinstance(value, int):
            # (Enum.__new__ looks in the value map before Flag._missing_ requires an int:
            # an equal float can find a declared member or an already cached pseudo-member)
            for key, member in self._value2member_map_.items():
                if key == value:
                    return member
            raise ValueError("%r is not a valid %s" % (value, self._cls_name_))
        hit = self._value2member_map_.get(value)
        if hit is not None:
            return hit
        return self._missing_(value)

    def _missing_(self, value: int):
        """
        Create a composite member containing all canonical members present in `value`.

        If non-member values are present, result depends on `_boundary_` setting.
        """
        # check boundaries
        # - value must be in range (e.g. -16 <-> +15, i.e. ~15 <-> 15)
        # - value must not include any skipped flags (e.g. if bit 2 is not
        #   defined, then 0d10 is invalid)
        flag_mask = self._flag_mask_
        singles_mask = self._singles_mask_
        all_bits = self._all_bits_
        neg_value = 0
        negative = False
        if (
                not ~all_bits <= value <= all_bits
                or value & (all_bits ^ flag_mask)
            ):
            if not self._keep_:
                max_bits = max(_bits(value), _bits(flag_mask))
                raise ValueError(
                        "%r invalid value %r\n    given %s\n  allowed %s" % (
                            self, value, _flag_bin(value, max_bits), _flag_bin(flag_mask, max_bits),
                            ))
            if value < 0:
                # Add the greater of the two powers of two to the negative value.
                # Its half fits even when the power is 2**63, so form the signed
                # result without first materializing an overflowing intermediate.
                half = max((all_bits >> 1) + 1, 2**(_bits(value) - 1))
                value = (value + half) + half
        if value < 0:
            neg_value = value
            negative = True
            value = (all_bits + value) + 1
        # get members and unknown
        unknown = value & ~flag_mask
        aliases = value & ~singles_mask
        member_value = value & singles_mask
        if unknown and not self._keep_:
            raise ValueError(
                    '%s(%r) -->  unknown values %r [%s]'
                    % (self._cls_name_, value, unknown, _flag_bin(unknown))
                    )
        name = ""
        if member_value or aliases:
            members = [m for m in self._member_list_ if m._value_ & member_value]
            combined_value = 0
            for m in members:
                combined_value |= m._value_
            if aliases:
                value = member_value | aliases
                for pm in self._member_map_.values():
                    if pm not in members and pm._value_ and pm._value_ & value == pm._value_:
                        members.append(pm)
                        combined_value |= pm._value_
            unknown = value ^ combined_value
            name = '|'.join([m._name_ for m in members])
            if not combined_value:
                name = ""
            elif unknown and not self._keep_:
                raise ValueError('%r: no members with value %r' % (self, unknown))
            elif unknown:
                name += '|%s' % repr(unknown)
        hit = self._value2member_map_.get(value)
        if hit is None:
            hit = __pys_enum_new(self._member_list_, name, value)
            self._value2member_map_[value] = hit
        if negative:
            self._value2member_map_[neg_value] = hit
        return hit

    def __contains__(self, value) -> bool:
        """Return True if `value` is in `cls`.

        `value` is in `cls` if:
        1) `value` is a member of `cls`, or
        2) `value` is the value of one of the `cls`'s members.
        3) `value` is a pseudo-member (flags)
        """
        if __pys_enum_is(value, self._member_list_):
            return True
        if isinstance(value, int):
            try:
                self(value)
                return True
            except ValueError:
                pass
        # (EnumType.__contains__ also tests the class's declared values. Cached pseudo-members
        # are not among them, even when a non-int value can now find one through __call__.)
        for member in self._member_map_.values():
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
        return MappingProxyType(self._member_map_)

    def __repr__(self) -> str:
        return "<flag %r>" % self._cls_name_


class Flag(Enum):
    """
    Support for flags
    """
    # (a flag class's members and pseudo-members are objects of its class; the compiler gives the
    # class _flag_type_(), its _FlagType object, and a pseudo-member without members a _name_ of
    # "", whose name is None)
    _value_: int

    @property
    def value(self) -> int:
        """The value of the Enum member."""
        return self._value_

    def _value_repr_(self) -> str:
        return repr(self._value_)

    @property
    def name(self) -> str | None:
        """The name of the Enum member."""
        return self._name_ if self._name_ != "" else None

    def __hash__(self) -> int:
        return hash(self._name_) if self._name_ != "" else hash(None)

    def __contains__(self, other) -> bool:
        """
        Returns True if self has at least the same flags set as other.
        """
        members = self._flag_type_()._member_list_
        if not __pys_enum_is(other, members):
            raise TypeError(
                "unsupported operand type(s) for 'in': %r and %r" % (
                    type(other).__qualname__, self.__class__.__qualname__))
        return other._value_ & self._value_ == other._value_

    def __iter__(self):
        """
        Returns flags in definition order.
        """
        ft = self._flag_type_()
        value = self._value_
        if ft._flag_mask_ == ft._singles_mask_:
            # Canonical members, already in definition order.
            for member in ft._member_list_:
                if member._value_ & value:
                    yield member
        else:
            # The loader accepts unnamed bits only in value order. CPython looks
            # up each bit as iteration advances, so an intervening Flag(bit)
            # can change its result from None to a cached pseudo-member.
            bits = value & ft._flag_mask_
            while bits:
                bit = bits & -bits
                bits ^= bit
                yield ft._value2member_map_.get(bit)

    def __len__(self) -> int:
        return _bit_count(self._value_)

    def __repr__(self) -> str:
        cls_name = self.__class__.__name__
        if self._name_ == "":
            return "<%s: %s>" % (cls_name, self._value_repr_())
        else:
            return "<%s.%s: %s>" % (cls_name, self._name_, self._value_repr_())

    def __str__(self) -> str:
        cls_name = self.__class__.__name__
        if self._name_ == "":
            return '%s(%r)' % (cls_name, self._value_)
        else:
            return "%s.%s" % (cls_name, self._name_)

    def __bool__(self) -> bool:
        return self._value_ != 0

    def _flag_of_(self, other, op: str) -> int:
        # (Flag._get_value(): the value of a member of the class; else CPython's TypeError, once
        # the methods of both operands decline; an int on the left is a compile-time error, as
        # a flag has no reflected operator methods)
        members = self._flag_type_()._member_list_
        if __pys_enum_is(other, members):
            return other._value_
        raise TypeError("unsupported operand type(s) for %s: '%s' and '%s'" % (op, type(self).__name__, type(other).__name__))

    def __or__(self, other):
        return self._flag_type_()(self._value_ | self._flag_of_(other, '|'))

    def __and__(self, other):
        return self._flag_type_()(self._value_ & self._flag_of_(other, '&'))

    def __xor__(self, other):
        return self._flag_type_()(self._value_ ^ self._flag_of_(other, '^'))

    def __invert__(self):
        return self._flag_type_()(self._flag_type_()._singles_mask_ & ~self._value_)


def _intflag_of(x, a, op: str) -> int:
    # an operand of IntFlag member a's |, & or ^, as Flag._get_value() takes it for a class of int:
    # a member of a's class, or an int (also an int-like member); else CPython's TypeError
    if isinstance(x, int):
        return x
    if isinstance(x, IntEnum) or isinstance(x, IntFlag):
        return x._value_
    raise TypeError("unsupported operand type(s) for %s: '%s' and '%s'" % (op, type(a).__name__, type(x).__name__))


class IntFlag(Flag):
    """
    Support for integer-based Flags
    """
    # (CPython's IntFlag(int, ReprEnum, Flag, boundary=KEEP): a member is an object of its class
    # with int's operations, str() and format(), as an IntEnum member is; |, & and ^ with an int
    # keep the class, whose boundary KEEP keeps bits that no member has)

    def __str__(self) -> str:
        return repr(self._value_)

    def __format__(self, format_spec: str) -> str:
        # (int's and str's __format__: with an empty spec, str() of the object, which a class's
        # own __str__ makes)
        if format_spec == "":
            return str(self)
        return format(self._value_, format_spec)

    def __hash__(self) -> int:
        return hash(self._value_)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, IntEnum) or isinstance(other, IntFlag):
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

    def __lshift__(self, other):
        return self._value_ << _int_of(other, self, '<<')

    def __rshift__(self, other):
        return self._value_ >> _int_of(other, self, '>>')

    def __or__(self, other):
        return self._flag_type_()(self._value_ | _intflag_of(other, self, '|'))

    def __and__(self, other):
        return self._flag_type_()(self._value_ & _intflag_of(other, self, '&'))

    def __xor__(self, other):
        return self._flag_type_()(self._value_ ^ _intflag_of(other, self, '^'))

    def __invert__(self):
        return self._flag_type_()(~self._value_)

    def __radd__(self, other):
        return _int_left(other, self, '+') + self._value_

    def __rsub__(self, other):
        return _int_left(other, self, '-') - self._value_

    def __rmul__(self, other):
        return _int_left(other, self, '*') * self._value_

    def __rtruediv__(self, other):
        return _int_left(other, self, '/') / self._value_

    def __rfloordiv__(self, other):
        return _int_left(other, self, '//') // self._value_

    def __rmod__(self, other):
        return _int_left(other, self, '%') % self._value_

    def __rlshift__(self, other):
        return _int_left(other, self, '<<') << self._value_

    def __rrshift__(self, other):
        return _int_left(other, self, '>>') >> self._value_

    def __ror__(self, other):
        return self._flag_type_()(_intflag_of(other, self, '|') | self._value_)

    def __rand__(self, other):
        return self._flag_type_()(_intflag_of(other, self, '&') & self._value_)

    def __rxor__(self, other):
        return self._flag_type_()(_intflag_of(other, self, '^') ^ self._value_)

    def __neg__(self) -> int:
        return -self._value_

    def __pos__(self) -> int:
        return self._value_

    def __abs__(self) -> int:
        return abs(self._value_)

    def __int__(self) -> int:
        return self._value_

    def __index__(self) -> int:
        return self._value_

    def __float__(self) -> float:
        return float(self._value_)


def unique(enumeration):
    """
    Class decorator for enumerations ensuring unique member values.
    """
    # (the compiler checks the members of an enum class that @unique decorates, and reports its
    # aliases as an error: CPython's ValueError where the class statement runs)
    return enumeration
