# error: module 'weakref' has no attribute 'proxy'
import weakref


class Item:
    def get(self) -> int:
        return 1


item = Item()
p = weakref.proxy(item)
