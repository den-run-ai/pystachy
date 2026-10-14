# Module import names exist only after their import executes (#283), including builtin
# aliases, aliases read through another module and a from-import of an absent alias.
import sys

import good


def boom() -> None:
    raise ValueError("boom")


try:
    print(early.A)
except NameError as e:
    print("early:", e)
import good as early

print("bound:", early.A)
if len(sys.argv) > 5:
    import good as conditional
    from good import A2 as conditional_fn
for _ in range(len(sys.argv) - 3):
    import good as loop_alias
try:
    print(conditional.A)
except NameError as e:
    print("conditional:", e)
try:
    print(conditional_fn())
except NameError as e:
    print("function:", e)
try:
    print(loop_alias.A)
except NameError as e:
    print("loop:", e)

try:
    boom()
    import math as skipped_math
    from math import tau as skipped_tau
except ValueError:
    pass
try:
    print(skipped_math.pi)
except NameError as e:
    print("builtin:", e)
try:
    print(skipped_math.sqrt(4.0))
except NameError as e:
    print("builtin call:", e)
try:
    print(skipped_tau)
except NameError as e:
    print("builtin constant:", e)
import math as skipped_math
from math import tau as skipped_tau

print("builtin bound:", skipped_math.sqrt(4.0), skipped_tau > 6.0)

# A plain mixed import binds each alias in order, even when a later import fails.
try:
    import bad, math as later_math
except ValueError:
    print("first import failed")
try:
    print(later_math.pi)
except NameError as e:
    print("later:", e)
try:
    import math as earlier_math, bad
except ValueError:
    print("last import failed")
print("earlier bound:", earlier_math.pi > 3.0)


def local(skip: bool) -> None:
    try:
        if skip:
            boom()
        import math as lm
        from math import sqrt as lsqrt
    except ValueError:
        pass
    try:
        print("local:", lm.pi > 3.0, lsqrt(4.0))
    except UnboundLocalError as e:
        print("local:", e)


local(True)
local(False)

import guarded_bindings

try:
    print(guarded_bindings.ua2())
except AttributeError as e:
    print("module function:", e)
try:
    print(guarded_bindings.g.A)
except AttributeError as e:
    print("module alias:", e)
try:
    print(guarded_bindings.m.pi)
except AttributeError as e:
    print("module builtin:", e)
try:
    print(guarded_bindings.tau)
except AttributeError as e:
    print("module constant:", e)
def from_missing() -> int:
    from guarded_bindings import ua2 as absent

    return absent()


try:
    print(from_missing())
except ImportError:
    print("from module: ImportError")
print("present:", guarded_bindings.present())
from guarded_bindings import present as shared, present2 as shared

print("duplicate alias:", shared())
for _ in range(2):
    try:
        import guard_retry
    except ValueError:
        print("retry failed")
