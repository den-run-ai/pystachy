# list.remove() of a float that no int equals raises CPython's ValueError
xs = [1, 2]
xs.remove(2.0)
print(xs)
xs.remove(1.5)
