# pystachy: python-int
# A bytearray in a module whose ints promote: the sizes, indexes, byte values, counts and slice
# bounds it is given are promoting ints, which its buffer's operations take as 64-bit ints.


def main() -> None:
    n = 3
    b = bytearray(n)
    b[n - 1] = 255
    b.append(n * 20)
    b += bytes([n])
    b.insert(n - 2, 7)
    print(b, len(b), b[n], b[-n], b == bytearray(b"\x00\x07\x00\xff<\x03"), b != b.copy())
    print(b.find(60), b.index(255, n), b.count(0), n in b, b[1:n], b[::n - 1], b * (n - 1))
    big = 2 ** 70
    b[0] = big % 251
    b[n:n + 2] = bytes([big % 7, big % 11])
    del b[n - 3]
    print(b, sum(b) + big, b.pop(n - 2), bytearray([n, big % 13]) + b, b.zfill(n * 3))
    try:
        b[n * 4] = 1
    except IndexError as e:
        print("IndexError:", e)
    try:
        b.append(n * 100)
    except ValueError as e:
        print("ValueError:", e)


main()
