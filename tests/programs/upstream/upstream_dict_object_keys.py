# Adapted from CPython 3.13.16 Lib/test/test_dict.py, class DictTest: the object keys of
# test_getitem, test_setdefault and test_pop (BadEq, BadHash), test_setdefault_atomic,
# test_setitem_atomic_at_resize, test_mutating_lookup, test_eq's BadCmp, test_bad_key and
# test_resize2, commit cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256:
# ab8c3107f3390867750c19a3024c0284c34c62fb6f2297024627b1c66b48d406.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertTrue(c) and assertEqual(a, b)
# print whether they hold and assert it, assertRaises a try statement that prints the
# exception's class. Test-local classes are module classes. A dict holds one key type, so where
# upstream mixes int keys with objects (d[23], {hashed1: 5, 0: 0, ...}, {1: 1}, d[9] = 6) the int
# is an object of a sibling class with the int's hash (and where upstream's value types mix, the
# values are ints or lists of ints). A class attribute an object then assigns (fail,
# mutate_dict) is an __init__ field or a module list; id(a) == id(b) is a is b, hash(self.__class__)
# a constant (all that matters is that the keys' hashes are equal), and test_bad_key's exec() of
# each statement is that statement. The other object keys of test_dict.py stay out (see
# tests/programs/upstream/upstream_dict_methods.py): test_merge_and_mutate (an __eq__ that empties the dict merged
# from: CPython's RuntimeError "dict mutated during update" is not raised, and its keys mix ints
# and objects), test_equal_operator_modifying_operand (__del__), test_dictitems_contains_use_after_free
# (NotImplemented, items views), test_init_use_after_free (dict() of a list of mixed pairs).


class Exc(Exception):
    pass


class CustomException(Exception):
    pass


def check(label: str, ok: bool) -> None:
    print(label, ok)
    assert ok, label


class Key:
    pass


class BadEq(Key):
    def __eq__(self, other: object) -> bool:
        raise Exc()

    def __hash__(self) -> int:
        return 24


class Int23(Key):
    # (the int 23, which upstream looks up: its hash, and no __eq__ of its own)
    def __hash__(self) -> int:
        return 23


class BadHash(Key):
    def __init__(self) -> None:
        self.fail = False

    def __hash__(self) -> int:
        if self.fail:
            raise Exc()
        else:
            return 42


def test_getitem() -> None:
    d: dict[Key, int] = {}
    d[BadEq()] = 42
    try:
        d[Int23()]
    except KeyError:
        print("KeyError")
    x = BadHash()
    d[x] = 42
    x.fail = True
    try:
        d[x]
    except Exc:
        print("Exc")


def test_setdefault() -> None:
    d: dict[BadHash, list[int]] = {}
    x = BadHash()
    d[x] = [42]
    x.fail = True
    try:
        d.setdefault(x, [])
    except Exc:
        print("Exc")


class HKey:
    pass


class Hashed(HKey):
    def __init__(self) -> None:
        self.hash_count = 0
        self.eq_count = 0

    def __hash__(self) -> int:
        self.hash_count += 1
        return 42

    def __eq__(self, other: object) -> bool:
        self.eq_count += 1
        return self is other


class SmallInt(HKey):
    # (the ints 0 to 3 of test_setitem_atomic_at_resize: their hashes)
    def __init__(self, i: int) -> None:
        self.i = i

    def __hash__(self) -> int:
        return self.i


def test_setdefault_atomic() -> None:
    # Issue #13521: setdefault() calls __hash__ and __eq__ only once.
    hashed1 = Hashed()
    y = {hashed1: 5}
    hashed2 = Hashed()
    y.setdefault(hashed2, 0)
    check("hashed1.hash_count == 1", hashed1.hash_count == 1)
    check("hashed2.hash_count == 1", hashed2.hash_count == 1)
    check("eq_count == 1", hashed1.eq_count + hashed2.eq_count == 1)


def test_setitem_atomic_at_resize() -> None:
    hashed1 = Hashed()
    # 5 items
    y: dict[HKey, int] = {hashed1: 5, SmallInt(0): 0, SmallInt(1): 1, SmallInt(2): 2, SmallInt(3): 3}
    hashed2 = Hashed()
    # 6th item forces a resize
    y[hashed2] = 6
    check("hashed1.hash_count == 1", hashed1.hash_count == 1)
    check("hashed2.hash_count == 1", hashed2.hash_count == 1)
    check("eq_count == 1", hashed1.eq_count + hashed2.eq_count == 1)


def test_pop() -> None:
    d: dict[BadHash, int] = {}
    x = BadHash()
    d[x] = 42
    x.fail = True
    try:
        d.pop(x)
    except Exc:
        print("Exc")


class NastyKey:
    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        # hash collision!
        return 1

    def __eq__(self, other: "NastyKey") -> bool:
        if len(mutate_dict) > 0:
            mydict, key = mutate_dict.pop()
            del mydict[key]
        return self.value == other.value


mutate_dict: list[tuple[dict[NastyKey, int], NastyKey]] = []


def test_mutating_lookup() -> None:
    # changing dict during a lookup (issue #14417)
    key1 = NastyKey(1)
    key2 = NastyKey(2)
    d = {key1: 1}
    mutate_dict.append((d, key1))
    d[key2] = 2
    check("d == {key2: 2}", d == {key2: 2})


class BadCmp:
    def __eq__(self, other: object) -> bool:
        raise Exc()

    def __hash__(self) -> int:
        return 1


def test_eq() -> None:
    d1 = {BadCmp(): 1}
    d2 = {BadCmp(): 1}
    try:
        d1 == d2
    except Exc:
        print("Exc")


class BadDictKey:
    def __hash__(self) -> int:
        return 7

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BadDictKey):
            raise CustomException
        return False


def test_bad_key() -> None:
    # Dictionary lookups should fail if __eq__() raises an exception.
    d: dict[BadDictKey, int] = {}
    x1 = BadDictKey()
    x2 = BadDictKey()
    d[x1] = 1
    try:
        d[x2] = 2
    except CustomException:
        print("d[x2] = 2: CustomException")
    try:
        z = d[x2]
        print(z)
    except CustomException:
        print("z = d[x2]: CustomException")
    try:
        x2 in d
    except CustomException:
        print("x2 in d: CustomException")
    try:
        d.get(x2)
    except CustomException:
        print("d.get(x2): CustomException")
    try:
        d.setdefault(x2, 42)
    except CustomException:
        print("d.setdefault(x2, 42): CustomException")
    try:
        d.pop(x2)
    except CustomException:
        print("d.pop(x2): CustomException")
    try:
        d.update({x2: 2})
    except CustomException:
        print("d.update({x2: 2}): CustomException")


resizing = [False]


class XBase:
    pass


class X(XBase):
    def __hash__(self) -> int:
        return 5

    def __eq__(self, other: object) -> bool:
        if resizing[0]:
            d2.clear()
        return False


class Nine(XBase):
    # (the int 9: its hash)
    def __hash__(self) -> int:
        return 9


d2: dict[XBase, int] = {}


def test_resize2() -> None:
    # Another dict resizing bug (SF bug #1456209).
    # This caused Segmentation faults or Illegal instructions.
    d2[X()] = 1
    d2[X()] = 2
    d2[X()] = 3
    d2[X()] = 4
    d2[X()] = 5
    # now trigger a resize
    resizing[0] = True
    d2[Nine()] = 6
    print(len(d2))


test_getitem()
test_setdefault()
test_setdefault_atomic()
test_setitem_atomic_at_resize()
test_pop()
test_mutating_lookup()
test_eq()
test_bad_key()
test_resize2()
