# collections.abc's Mapping and MutableMapping (and typing's) take lib/collections' mappings,
# which derive from dict in CPython, for mappings: but no Sequence
import collections.abc
import typing
from collections import Counter, OrderedDict, defaultdict
from collections.abc import Mapping, MutableMapping, Sequence

dd: defaultdict[str, int] = defaultdict(int)
od: OrderedDict[str, int] = OrderedDict()
c = Counter("ab")
print(isinstance(dd, Mapping), isinstance(od, MutableMapping), isinstance(c, collections.abc.Mapping))
print(isinstance(dd, typing.Mapping), isinstance(c, typing.MutableMapping), isinstance(od, Sequence))
