# list.index(None) on a list of str: ValueError, as None is not in it
xs = ["a"]
print(xs.count(None), None in xs)
print(xs.index(None))
