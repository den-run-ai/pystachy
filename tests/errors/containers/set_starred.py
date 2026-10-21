# error: set_starred.py:3: error: unpacking in a set display ({*xs}) is not supported: use set(xs) or s.update(xs)
xs = [1, 2]
s = {*xs, 3}
print(s)
