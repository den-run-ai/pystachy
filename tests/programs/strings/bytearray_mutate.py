# a bytearray's changes in place: items, append, extend, insert, pop, remove, reverse, += and *=,
# with their errors, which leave it as it was


def show(tag: str, b: bytearray) -> None:
    print(tag, b, len(b))


b = bytearray(b"hello")
b[0] = 72
b[-1] = 79
show("set", b)
del b[1]
del b[-1]
show("del", b)
b.append(33)
b.extend(b" wor")
b.extend(bytearray(b"ld"))
b.extend([46, 46])
b.extend(list(range(48, 51)))
b.extend(x + 1 for x in [0, 1])
b.extend((9,))
show("extend", b)
b.extend(b)
show("self", b)
b.insert(0, 62)
b.insert(len(b), 60)
b.insert(-1, 45)
b.insert(-1000, 1)
b.insert(1000, 2)
show("insert", b)
print(b.pop(), b.pop(0), b.pop(-2), b.pop(3))
show("pop", b)
b.remove(108)
b.remove(46)
show("remove", b)
b.reverse()
show("reverse", b)
c = b
b += b"+="
b += bytearray(b"ba")
try:
    b += b
except BufferError as err:
    print("BufferError:", err)
nothing = bytearray()
nothing += nothing
show("iadd", b)
print(c is b)
b *= 2
show("imul", b)
print(c is b, len(c))
b *= 0
show("imul0", b)
d = bytearray(b"ab")
print(d + b"cd", d + bytearray(b"ef"), d + d, d * 3, d * 0, d * -1, (d + b"x") is d, d)
e = bytearray(b"x")
e.reverse()
bytearray().reverse()
show("one", e)

for bad in [256, -1, 1000]:
    t = bytearray(b"abc")
    for what in ["append", "setitem", "insert", "remove", "extend"]:
        try:
            if what == "append":
                t.append(bad)
            elif what == "setitem":
                t[1] = bad
            elif what == "insert":
                t.insert(1, bad)
            elif what == "remove":
                t.remove(bad)
            else:
                t.extend([65, bad, 66])
        except ValueError as err:
            print(what, bad, "ValueError:", err, t)
t = bytearray(b"abc")
for i in [3, -4, 100]:
    try:
        t[i] = 1
    except IndexError as err:
        print("set IndexError:", err)
    try:
        del t[i]
    except IndexError as err:
        print("del IndexError:", err)
    try:
        print(t[i])
    except IndexError as err:
        print("get IndexError:", err)
    try:
        t.pop(i)
    except IndexError as err:
        print("pop IndexError:", err)
try:
    bytearray().pop()
except IndexError as err:
    print("IndexError:", err)
try:
    t.remove(120)
except ValueError as err:
    print("ValueError:", err)
try:
    t += [1, 2]
except TypeError as err:
    print("TypeError:", err)
try:
    t += "text"
except TypeError as err:
    print("TypeError:", err)
try:
    print(t + 3)
except TypeError as err:
    print("TypeError:", err)
show("after", t)

big = bytearray()
total = 0
for i in range(5000):
    big.append(i % 256)
    if i % 7 == 0:
        big.extend(b"xyz")
    if i % 11 == 0:
        total += big.pop()
    if i % 13 == 0:
        big.insert(i % (len(big) + 1), 7)
    if i % 17 == 0:
        del big[i % len(big)]
print(len(big), total, sum(big), bytes(big[:12]), bytes(big[-12:]))
snapshot = bytes(big)
big[0] = 200
big.append(1)
print(snapshot[0], big[0], len(snapshot), len(big), snapshot == bytes(big))
