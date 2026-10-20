# Template methods of an imported module's classes: compiled for each call's argument types, and
# one that cannot compile (Acc.broken) is an error only where the program calls it
from mods.tmeth import Acc, Oops, Rec, Worse
import mods.tmeth

a = Acc(1)
print(a.add(2).add(3).total, a.describe("t"), a.describe("t", " = "), a.each(1, 2, z=0, y=0))
try:
    raise Worse("bad")
except Oops as e:
    print(e.detail(1), e.detail("x"), type(e).__name__)
print(mods.tmeth.Acc(5).describe("n", sep=""), mods.tmeth.Acc(0).each(1.5))
print(Rec(1), Rec(1).plus(2), Rec(2).plus(0.5))
