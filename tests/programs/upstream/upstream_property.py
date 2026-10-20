# Adapted from CPython 3.13.16 Lib/test/test_property.py: PropertyTests.
# test_property_decorator_subclass and _PropertyUnreachableAttribute.test_set_property, commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name; assertRaises(E, getattr/setattr/delattr,
# obj, "spam", ...) is a try statement around obj.spam, obj.spam = ... and del obj.spam that
# prints the exception. The properties' getters and setters are annotated (a property needs a
# return annotation); SubClass's getter is a @property of its own where upstream decorates it
# with @BaseClass.spam.getter (rejected: "unsupported decorator @BaseClass.spam.getter"), and its
# setter gets 0 where upstream sets None (an int property). test_set_property's class `cls` has
# a property with a getter and no setter, where upstream's is property() (no getter either).
# EXCLUDED upstream cases:
# - test_property_decorator_baseclass: BaseClass's deleter deletes an instance attribute
#   (rejected: "del of an attribute is only supported for a property (which calls its
#   deleter)"), and it uses delattr()/hasattr() of a name ("unsupported call
#   delattr(BaseClass,str)")
# - @x.getter (rejected: "unsupported decorator @spam.getter: define the property's getter once,
#   with @property") and @Base.x.getter: test_property_getter_doc_override, PropertyDocSub,
#   PropertySubNewGetter, PropertyNewGetter
# - property() called as a function (rejected: "property() called as a function is not
#   supported: decorate the getter with @property and the setter with @x.setter"):
#   PropertyDocBase, test_property_builtin_doc_writable, test_property_name's bar and baz,
#   test_get_property and test_del_property of property(); @foo.setter on a method of another
#   name (rejected: "@foo.setter on method oof is not supported: a property's setter takes its
#   name (foo) ..."); __doc__, __name__ and __isabstractmethod__ of property objects
#   (rejected: "'BaseClass' object has no attribute '__class__'"), refleak and pickling tests,
#   PropertySubclassTests (subclasses of property)
class PropertyBase(Exception):
    pass

class PropertyGet(PropertyBase):
    pass

class PropertySet(PropertyBase):
    pass

class PropertyDel(PropertyBase):
    pass

class BaseClass(object):
    def __init__(self):
        self._spam = 5

    @property
    def spam(self) -> int:
        """BaseClass.getter"""
        return self._spam

    @spam.setter
    def spam(self, value: int) -> None:
        self._spam = value

    @spam.deleter
    def spam(self) -> None:
        del self._spam


class SubClass(BaseClass):

    @property
    def spam(self) -> int:
        """SubClass.getter"""
        raise PropertyGet(self._spam)

    @spam.setter
    def spam(self, value: int) -> None:
        raise PropertySet(self._spam)

    @spam.deleter
    def spam(self) -> None:
        raise PropertyDel(self._spam)


def test_property_decorator_subclass() -> None:
    sub = SubClass()
    try:
        sub.spam
    except PropertyGet as e:
        print("PropertyGet", e)
    try:
        sub.spam = 0
    except PropertySet as e:
        print("PropertySet", e)
    try:
        del sub.spam
    except PropertyDel as e:
        print("PropertyDel", e)


class cls:
    @property
    def foo(self) -> int:
        return 1


def test_set_property() -> None:
    obj = cls()
    try:
        obj.foo = None
    except AttributeError as e:
        print("AttributeError:", e)


test_property_decorator_subclass()
test_set_property()
