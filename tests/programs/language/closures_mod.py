# Closures across modules: lambdas and defs of another module, returned, passed back and called
import mods.closmod
from mods.closmod import noop, pipeline, scaled, tally

print(noop(4), mods.closmod.twice(scaled(2), 1), scaled(1)(5))
print(tally(["b", "a", "b", "c", "a", "b"]))
inc = lambda v: v + 1
print(pipeline(inc, inc, inc)(4), pipeline(scaled(2))(7), pipeline()(7), mods.closmod.keyed([3, 1, 2]), mods.closmod.keyed([3, 1, 2], key=noop))
