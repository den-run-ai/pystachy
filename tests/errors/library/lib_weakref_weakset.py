# error: class _weakrefset.WeakSet is not supported: cannot infer the type of class attribute '__sub__'
import weakref


class Item:
    def get(self) -> int:
        return 1


item = Item()
s = weakref.WeakSet()
