# pystachy: python-int
# Promoting ints (docs/python-int.md) through quoted and Final annotations, in this module and in
# an imported one, and into a module that does not opt in through quoted annotations.
from typing import Final

import spellings
from quoted_fixed import halve

TOP: Final = 3 ** 50


def local(x: "int") -> "int":
    y: "int" = x * x
    return y


print(spellings.quoted(2 ** 40), spellings.LIMIT, spellings.QLIMIT, spellings.Box(2 ** 40).value)
print(local(2 ** 40), TOP, TOP * TOP, halve(2 ** 62) * 2 ** 70, halve(local(2 ** 31)))
