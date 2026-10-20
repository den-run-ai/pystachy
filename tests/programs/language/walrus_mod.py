# Assignment expressions and starred targets in another module bind that module's names
import mods.walrusmod
from mods.walrusmod import count, h, rest

print(mods.walrusmod.count, count, mods.walrusmod.big, h, mods.walrusmod.input)
print(mods.walrusmod.bump(), mods.walrusmod.level, mods.walrusmod.bump(), mods.walrusmod.level)
print(mods.walrusmod.twice(), mods.walrusmod.square_sum(3), mods.walrusmod.scan([" a ", "", "b"]))
print(mods.walrusmod.head, rest)
