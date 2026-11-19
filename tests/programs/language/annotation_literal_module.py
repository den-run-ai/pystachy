# Literal[...] in an imported module: a Literal nested in another, by an alias or a qualified
# name, and a Literal that only an if TYPE_CHECKING: block imports where annotations are deferred
from mods.literal_deferred import Switch, flip, level
from mods.literal_types import flag, mode, repeat

print(mode("r"), repeat("a"), repeat("b", 2), flag(False))
s = Switch()
print(s.state, flip(s), flip(s), level(2))
