# error: class weakref.WeakKeyDictionary is not supported: unsupported base class
import weakref


class Item:
    def get(self) -> int:
        return 1


item = Item()
d = weakref.WeakKeyDictionary()
