# error: class weakref.WeakMethod is not supported: parameter 'meth' of method __new__() has no type annotation
# (WeakMethod derives from ref, a class template, and makes its objects in a __new__ of its own)
import weakref


class Item:
    def get(self) -> int:
        return 1


item = Item()
m = weakref.WeakMethod(item.get)
