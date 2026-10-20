# error: module 'weakref' has no attribute 'finalize'
import weakref


class Item:
    def get(self) -> int:
        return 1


item = Item()
f = weakref.finalize(item, print)
