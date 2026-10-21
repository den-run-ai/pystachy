# collections.namedtuple() classes of an imported module (tests/mods/ntmod.py): made from the
# calls of its top-level code, with their docstrings' assignments; objects made there and here
from mods.ntmod import Event, Key, ModuleInfo, Positions, mismatches, schedule
import mods.ntmod

print(mismatches([1, 2, 3], [1, 5, 4]), mismatches("ab", "ax")[0].expected)
print(ModuleInfo("finder", "m", False), ModuleInfo._fields, mods.ntmod.ModuleInfo("f", "n", True).ispkg)
e = schedule(2.5, "run")
print(e, e.kwargs["k"], Event._fields, e < schedule(3.0, "z"), Event(1.0, 2, 3, "a", (), {"x": 1.0}).time)
k = Key("f", 3, 1, "data")
print(k, mods.ntmod.SelectorKey._fields, k._replace(events=2), type(k).__name__, type(k).__module__)
print(Positions(), Positions(3), Positions._field_defaults, type(mods.ntmod._Mismatch(1, 2, 3)).__qualname__)
