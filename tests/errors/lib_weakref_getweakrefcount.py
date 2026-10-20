# error: module 'weakref' has no attribute 'getweakrefcount'
import weakref


class Item:
    def get(self) -> int:
        return 1


item = Item()
n = weakref.getweakrefcount(item)
