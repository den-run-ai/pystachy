# error: reflect_getattr_text_dataclass.py:11: error: the text of getattr(o, name) for a run-time name is not supported where o may be a Item, whose attribute __annotations__ Pystachy cannot print
# A run-time name may name any attribute, which the text needs: a dataclass's __annotations__ and __dataclass_fields__ are not printed
from dataclasses import dataclass


@dataclass
class Item:
    name: str


print(getattr(Item("a"), input(), None))
