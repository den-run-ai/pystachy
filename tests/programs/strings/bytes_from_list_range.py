# bytes(list): the items that fit, and ValueError for an item below 0 or above 255 wherever it
# is in the list, alone or among others, with the list unchanged afterwards
def show(xs: list[int]) -> None:
    try:
        b = bytes(xs)
        print(len(b), b[:8], b[-4:], sum(b))
    except ValueError as e:
        print("ValueError", e, len(xs), xs[:3], xs[-2:])


show([])
show([0])
show([255])
show([0, 1, 127, 128, 254, 255])
show(list(range(256)))
show([i % 256 for i in range(5000)])
for bad in [256, -1, 257, 1000, -256, 65536, 4294967296, -4294967296, 9223372036854775807, -9223372036854775807 - 1,
            4294967295, 1 << 62]:
    show([bad])
    show([bad, 1, 2])
    show([1, 2, bad])
    show([1, bad, 2] * 40)
    show(list(range(256)) + [bad])
# items that are in range each, whose bits together are too: every byte value twice
show([i // 2 for i in range(512)])
# two items out of range in opposite directions
show([1, -1, 256, 2])
show([256, -257])
xs = [72, 105, 300]
try:
    print(bytes(xs))
except ValueError as e:
    print("ValueError", e)
xs[2] = 33
print(bytes(xs), xs)
