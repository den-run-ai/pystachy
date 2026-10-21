import mods.alias_ready_cycle_a as source
from mods.alias_ready_cycle_a import Crate, plus, also

print(source.Crate(3).v, source.plus(3), source.also(3))
print(Crate(5).v, plus(5), also(5))
print(source.build(), source.invoke(), source.through_import())
