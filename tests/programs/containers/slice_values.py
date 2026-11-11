# Native slice values preserve raw bool/None bounds and normalize only when consumed.
def bounds(s: slice, length: int) -> None:
    print(repr(s), s.start, s.stop, s.step, s.indices(length))


bounds(slice(4), 6)
bounds(slice(None), 0)
bounds(slice(None, None, -1), 6)
bounds(slice(-99, 99, 2), 6)
bounds(slice(99, -99, -3), 6)
bounds(slice(True, False, True), 6)
bounds(slice(-9223372036854775808, 9223372036854775807, -9223372036854775808), 6)
for length in [0, 1, 7]:
    for start in [-10, -1, 0, 2, 10]:
        for stop in [-10, -1, 0, 2, 10]:
            for step in [-3, -1, 1, 2]:
                s = slice(start, stop, step)
                a, b, c = s.indices(length)
                assert list(range(a, b, c)) == list(range(length))[s]
print('indices matrix')
s = slice(None, None, -2)
print([1, 2, 3, 4, 5][s], 'abcde'[s], b'abcde'[s])
print(list(range(8)[s]))
print(isinstance(s, slice), s is s)
for n in [-1, 3]:
    try:
        print(slice(None, None, 0).indices(n))
    except ValueError as e:
        print(str(e))

print(slice(1, 3) == slice(1, 3), slice(1, 3) != slice(1, 4))
