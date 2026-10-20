# error: 'in' of a range needs an int, not float
# CPython compares a float with each item; Pystachy tests membership of ints arithmetically
r = range(3)
print(1.0 in r)
