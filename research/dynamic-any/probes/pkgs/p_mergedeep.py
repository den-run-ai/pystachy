# pystachy: dynamic-any
from mergedeep import merge
print(merge({}, {"db": {"host": "h", "port": 1}}, {"db": {"port": 2, "ssl": True}, "name": "x"}))
