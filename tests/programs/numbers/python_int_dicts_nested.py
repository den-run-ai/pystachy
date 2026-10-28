# pystachy: python-int
# get() calls nested 40 deep, in defaults and in keys, of dicts whose values may be past 64 bits.
# Compiling each call decides on its arguments' types, which must not compile them again at
# each level: that doubled the work per level (as #781 did for displays).
d = {0: 2 ** 64}
key = 5
print(d.get(0, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, 0)))))))))))))))))))))))))))))))))))))))))
e = {0: 1, 1: 0, 2: -2 ** 70}
print(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(e.get(0, 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), 0), d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, d.get(key, 0)))))))))))))))))))))))))))))))))))))))) - 1)
