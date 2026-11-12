# list(()) typed as a list of strs, then filled: its array must be one the collector scans, or
# the strs it holds are freed while in use.
names: list[str] = list(())
for i in range(2000):
    names.append("n" + str(i) * 3)
junk = []
for i in range(300000):
    junk.append(str(i) * 20)
total = 0
for s in names:
    total += len(s)
print(total, names[0], names[1999], len(junk))
numbers: list[int] = list(())
numbers.append(7)
print(numbers, list((1.5, 2.5)))
