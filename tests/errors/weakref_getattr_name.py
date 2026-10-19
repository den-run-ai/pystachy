# error: reflection of a weakref.ReferenceType object is not supported
# A name known only at run time could reach the module's own fields
import sys
from _weakref import ref


class Item:
    pass


item = Item()
name = sys.argv[0][:0] + "_handle"
print(getattr(ref(item), name))
