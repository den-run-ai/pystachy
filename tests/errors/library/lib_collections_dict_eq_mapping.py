# error: cannot compare dict[str,int] == collections.OrderedDict
# A mapping compares with a dict on its left (od == d); CPython also reflects d == od to it
from collections import OrderedDict

od = OrderedDict({"a": 1})
print({"a": 1} == od)
