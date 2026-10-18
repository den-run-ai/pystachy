# Prototype deliberately rejects operations it cannot give Python weak-reference semantics.
from _weakref import ref


class Item:
    pass


obj = Item()
r = ref(obj)
try:
    print(r == r)
except NotImplementedError as e:
    print(e)
try:
    print(r != r)
except NotImplementedError as e:
    print(e)
try:
    print(hash(r))
except NotImplementedError as e:
    print(e)
