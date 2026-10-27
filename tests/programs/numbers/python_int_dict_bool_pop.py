# pystachy: python-int
# pop() of a bool key, without a default, of a dict of ints that holds values past 64 bits: True
# and False find the keys 1 and 0, and one that the dict does not hold raises the KeyError that
# names it as the bool it is.
big = 2 ** 64
flagged: dict[int, int] = {1: 2, 2: big, 0: big * 3}
print(flagged.pop(True), flagged.pop(False), flagged)
try:
    flagged.pop(True)
except KeyError as e:
    print("KeyError:", e)
flagged[1] = big + 1
t = 2 > 1
print(flagged.pop(t), flagged.pop(t, 0), flagged)
try:
    flagged.pop(False)
except KeyError as e:
    print("KeyError:", e)
