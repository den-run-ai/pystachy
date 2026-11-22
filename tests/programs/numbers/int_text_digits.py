# str() of an int writes a number of every length an int has, a "-" before a negative one, and
# -2**63, whose magnitude no int holds. repr(), an f-string and "%d" give the same text, and
# int() reads it back
MAXI = 9223372036854775807
p = 1
lens: list[int] = []
for k in range(19):
    # 10**k, the least number of k + 1 digits, and its neighbours
    for v in [p - 1, p, p + 1, 1 - p, -p, -p - 1]:
        s = str(v)
        lens.append(len(s))
        if int(s) != v or repr(v) != s or f"{v}" != s or "%d" % v != s:
            print("differs", v, s)
    print(k, str(p), str(-p), str(p - 1))
    if k < 18:
        p *= 10
print(lens)
print(str(MAXI), str(MAXI - 1), str(-MAXI), str(-MAXI - 1))
print([str(v) for v in [0, -0, 7, -7, 10, -10, 99, 100, 255, -256, 65535, 4294967296, -4294967297]])
# each bit alone, and the ones below it
for k in range(0, 63, 7):
    b = 1 << k
    print(k, str(b), str(b - 1), str(-b), str(-b - 1))
# the strs stay what they were while more are made: each is its own, kept in a list
kept: list[str] = []
for i in range(-600, 600):
    kept.append(str(i * 7919))
total = 0
for i in range(-600, 600):
    if kept[i + 600] != str(i * 7919) or int(kept[i + 600]) != i * 7919:
        print("lost", i)
    total += len(kept[i + 600])
print(len(kept), total, kept[0], kept[599], kept[600], kept[1199])
