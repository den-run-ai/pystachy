# Adapted from CPython 3.13.16 Lib/test/test_weakref.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91 (SHA-256
# 500cd4b23e5c1d66d42910de90eec64c6e7968741d3dccfcce83cee8c3d339ef): class ReferencesTestCase's
# test_basic_ref, test_ref_repr, test_equality and test_hashing, ModuleTestCase.test_names, and the
# libreftest doctest example of a reference whose referent dies.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name (ModuleTestCase's is prefixed with its class,
# and reads the attributes of a reference's type, as a class object is not a value here);
# assertTrue(x), assertFalse(x), assertIs(a, b) and assertEqual(a, b) assert, and each function
# prints what it checked. weakref.ref is _weakref.ref: the weakref module does not import here
# (docs/prototypes/weakref.md). Object's __eq__ and __lt__ take an Object (upstream returns
# NotImplemented for another type, which is not a value here); C has a field, as a class without
# one has nothing to hold it apart. Where upstream drops the last owners and calls gc.collect(), whose
# reference counts free each referent at once, the test makes a cohort of referents, drops their
# owners, allocates without reading the references, and checks upstream's assertions on every
# reference whose referent died; at least one must (Pystachy's collector is a conservative tracing
# one, which may keep a few referents through stale stack words: see tests/lib_weakref_transition.py).
# A function reads its live referents last, as a native local is a root only until its last use.
# EXCLUDED upstream cases:
# - test_basic_ref's check_basic_ref(create_function) and check_basic_ref(create_bound_method):
#   references to functions and bound methods are not supported (ordinary class instances only)
# - test_ref_repr's WithName part, whose class's __name__ property CPython adds to the repr
# - test_equality's a == x and a != x (a reference compared with an object of another type, a
#   compile-time type error here) and a == ALWAYS_EQ
# - callbacks (test_basic_callback, test_multiple_callbacks, test_callback_* and the others that pass
#   one), proxies (test_proxy_*, test_basic_proxy, test_callable_proxy), reference reuse
#   (test_ref_reuse, test_shared_ref_without_callback), getweakrefcount() and getweakrefs(),
#   __callback__, weakrefs to classes and functions (test_classes, test_cfunction, test_init's
#   ref(Exception)), test_init's and test_constructor_kwargs' TypeErrors and test_ordering's (compile-
#   time errors here), gc thresholds and __del__ (test_gc_during_*, test_ref_created_during_del,
#   test_callback_gcs), and the WeakMethod, mapping, WeakSet and finalize classes
# - ModuleTestCase.test_names for ProxyType, CallableProxyType, WeakMethod, WeakSet,
#   WeakKeyDictionary and WeakValueDictionary, which _weakref does not have
import re
from _weakref import ReferenceType, ref


class C:
    def __init__(self):
        self.tag = 0

    def method(self) -> None:
        pass


class Object:
    def __init__(self, arg: int):
        self.arg = arg

    def __repr__(self) -> str:
        return "<Object %r>" % self.arg

    def __eq__(self, other: "Object") -> bool:
        return self.arg == other.arg

    def __lt__(self, other: "Object") -> bool:
        return self.arg < other.arg

    def __hash__(self) -> int:
        return hash(self.arg)


def churn() -> None:
    # (allocation pressure that reads no reference: see the header)
    for i in range(1024):
        text = str(i) * 65536
        assert len(text) >= 65536


def check_basic_ref() -> None:
    o = C()
    r = ref(o)
    assert r() is not None, "weak reference to live object should be live"
    o2 = r()
    assert o is o2, "<ref>() should return original object if live"
    o.tag = 1


def make_cs(n: int) -> list[C]:
    return [C() for i in range(n)]


def test_basic_ref() -> None:
    check_basic_ref()
    # Just make sure the tp_repr handler doesn't raise an exception.
    # Live reference:
    o = C()
    wr = ref(o)
    repr(wr)
    o.tag = 1
    # Dead reference: (a cohort, see the header)
    owners = make_cs(64)
    wrs = [ref(c) for c in owners]
    owners.clear()
    churn()
    dead = [w for w in wrs if w() is None]
    for w in dead:
        repr(w)
    print("test_basic_ref", len(dead) > 0)


def test_ref_repr() -> None:
    obj = C()
    r = ref(obj)
    regex = r"<weakref at 0x[0-9a-fA-F]+; to 'C' at 0x[0-9a-fA-F]+>"
    assert re.fullmatch(regex, repr(r)) is not None
    obj.tag = 1
    owners = make_cs(64)
    wrs = [ref(c) for c in owners]
    owners.clear()
    churn()
    dead = [w for w in wrs if w() is None]
    assert all(re.fullmatch(r"<weakref at 0x[0-9a-fA-F]+; dead>", repr(w)) is not None for w in dead)
    print("test_ref_repr", len(dead) > 0)


def make_objects(args: list[int]) -> list[Object]:
    return [Object(arg) for arg in args]


def test_equality() -> None:
    # Alive weakrefs defer equality testing to their underlying object.
    xs = make_objects([1] * 64)
    ys = make_objects([1] * 64)
    zs = make_objects([2] * 64)
    a_s = [ref(x) for x in xs]
    b_s = [ref(y) for y in ys]
    c_s = [ref(z) for z in zs]
    d_s = [ref(x) for x in xs]
    # Note how we directly test the operators here, to stress both
    # __eq__ and __ne__.
    for i in range(len(xs)):
        a = a_s[i]
        b = b_s[i]
        c = c_s[i]
        d = d_s[i]
        assert a == b
        assert not (a != b)
        assert not (a == c)
        assert a != c
        assert a == d
        assert not (a != d)
    xs.clear()
    ys.clear()
    zs.clear()
    churn()
    dead = [i for i in range(len(a_s)) if a_s[i]() is None and b_s[i]() is None and c_s[i]() is None]
    for i in dead:
        a = a_s[i]
        b = b_s[i]
        c = c_s[i]
        d = d_s[i]
        # Sanity check
        for r in [a, b, c]:
            assert r() is None
        # Dead weakrefs compare by identity: whether `a` and `d` are the
        # same weakref object is an implementation detail, since they pointed
        # to the same original object and didn't have a callback.
        # (see issue #16453).
        assert not (a == b)
        assert a != b
        assert not (a == c)
        assert a != c
        assert (a == d) == (a is d)
        assert (a != d) == (a is not d)
    print("test_equality", len(dead) > 0)


def test_hashing() -> None:
    # Alive weakrefs hash the same as the underlying object
    xs = make_objects([42] * 64)
    ys = make_objects([42] * 64)
    a_s = [ref(x) for x in xs]
    b_s = [ref(y) for y in ys]
    for a in a_s:
        assert hash(a) == hash(42)
    xs.clear()
    ys.clear()
    churn()
    dead = [i for i in range(len(a_s)) if a_s[i]() is None and b_s[i]() is None]
    # Dead weakrefs:
    # - retain their hash is they were hashed when alive;
    # - otherwise, cannot be hashed.
    for i in dead:
        assert hash(a_s[i]) == hash(42)
        try:
            hash(b_s[i])
            assert False, "TypeError not raised"
        except TypeError:
            pass
    print("test_hashing", len(dead) > 0)


def ModuleTestCase_test_names() -> None:
    # (getattr(weakref, name) is a class object, not a value here: its type's attributes are read)
    c = C()
    obj = ref(c)
    assert type(obj).__module__ == "weakref"
    assert type(obj).__name__ == "ReferenceType"
    assert type(obj).__qualname__ == "ReferenceType"
    print("ModuleTestCase_test_names", ReferenceType.__name__, ref.__name__, c.tag)


def libreftest_dead_reference() -> None:
    # >>> o = Object(); r = weakref.ref(o); o2 = r(); o is o2  -> True
    # >>> del o, o2; gc_collect(); print(r())                  -> None
    owners = make_cs(64)
    refs = [ref(o) for o in owners]
    print(all(refs[i]() is owners[i] for i in range(len(owners))))
    owners.clear()
    churn()
    print(any(r() is None for r in refs))


test_basic_ref()
test_ref_repr()
test_equality()
test_hashing()
ModuleTestCase_test_names()
libreftest_dead_reference()
