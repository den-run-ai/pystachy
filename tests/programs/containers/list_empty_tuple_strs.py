# list(()) typed as a list of strs must keep its items alive. A small retained list and
# large short-lived strings trigger ordinary collections without quadratic GC-stress work.
names: list[str] = list(())
for i in range(64):
    names.append("n" + str(i) * 3)
junk = 0
for i in range(48):
    junk += len(str(i) * 1048576)
total = 0
for s in names:
    total += len(s)
print(total, names[0], names[63], junk)
numbers: list[int] = list(())
numbers.append(7)
print(numbers, list((1.5, 2.5)))
