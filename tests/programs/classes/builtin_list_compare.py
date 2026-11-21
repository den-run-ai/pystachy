# Comparisons of list subclasses' objects follow CPython's rich comparison, one operator at a
# time: a class that defines __eq__ alone still compares != as list does (list.__ne__ is
# inherited, not derived from __eq__), and a right operand whose class derives from list is
# asked first, by the reflected method, where its class defines that method.


class Eq(list[int]):
    def __eq__(self, other: object) -> bool:
        return len(self) == 1


class Gt(list[int]):
    def __gt__(self, other: list[int]) -> bool:
        return True


class Plain(list[int]):
    pass


e = Eq([1])
print(e == [2], e != [2], e == Eq([3, 4]), e != Eq([3]), e != [1], Eq([1, 2]) == [1, 2])
g = Gt([1])
print(g > [5], g < [5], g >= [5], g <= [5], [5] < g, [5] > g, [0] <= g)
p = Plain([1, 2])
print(p == [1, 2], p != [1, 2], [1, 2] == p, [1, 2] != p, p < [1, 3], [1, 3] > p, p <= Plain([1, 2]), p == Plain([1, 2]))
print([] == Plain(), [] != p, Plain() == [], p != [], [] < p, p > [])
rows = [Plain([2]), Plain([1, 5]), Plain([1])]
print(sorted(rows), max(rows), min(rows), Plain([1]) in rows, rows.index(Plain([1, 5])), rows.count(Plain([2])))
