# error: class weakref.WeakMethod is not supported: inheritance with generic class templates is not supported
import weakref


class Item:
    def get(self) -> int:
        return 1


item = Item()
m = weakref.WeakMethod(item.get)
