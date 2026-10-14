def boom() -> None:
    raise ValueError("boom")


try:
    boom()
    from good import A2 as ua2
    import good as g
    import math as m
    from math import tau
except ValueError:
    pass

from good import A2 as present
from good import A2 as present2
