# gc (lib/_pystachy_gc.py, which Pystachy loads for CPython's C module): the settings that
# CPython keeps (enable(), disable(), thresholds, debug flags), with its values and errors,
# freeze() and unfreeze(), and collect(), whose count is at least 0.
import gc

print(gc.isenabled())
gc.disable()
print(gc.isenabled())
gc.disable()
gc.enable()
print(gc.isenabled())

print(gc.get_threshold())
gc.set_threshold(5)
print(gc.get_threshold())
gc.set_threshold(1, 2)
print(gc.get_threshold())
gc.set_threshold(200 * 1000, 30, 30)
print(gc.get_threshold())
gc.set_threshold(0, -1, -1)
t0, t1, t2 = gc.get_threshold()
print(t0, t1, t2)

print(gc.get_debug(), gc.DEBUG_STATS, gc.DEBUG_COLLECTABLE, gc.DEBUG_UNCOLLECTABLE, gc.DEBUG_SAVEALL, gc.DEBUG_LEAK)
print(gc.DEBUG_LEAK == gc.DEBUG_COLLECTABLE | gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_SAVEALL)
gc.set_debug(0)
print(gc.get_debug())

for generation in (3, -1, 100):
    try:
        gc.collect(generation)
        print("no error")
    except ValueError as e:
        print("ValueError", e)
print(gc.collect() >= 0, gc.collect(0) >= 0, gc.collect(1) >= 0, gc.collect(generation=2) >= 0)

# as mypy's build does around its loading of a cache
gc.disable()
data = [[i, i + 1] for i in range(1000)]
gc.freeze()
gc.unfreeze()
gc.enable()
print(len(data), gc.isenabled())
