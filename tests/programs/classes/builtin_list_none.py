# An object of a list subclass may be None, as any object may: each operation the class leaves
# to list raises CPython's own error for None, the one list's code raises for a list that is
# None (an index, a method, iteration, a builtin that iterates, unpacking, a comparison).


class S(list[int]):
    def top(self) -> int:
        return self[-1]


def get(flag: bool) -> S:
    return S([1, 2]) if flag else None


x = get(False)
print(x is None, x == [1], x != [1], repr(x), str(x), bool(x), not x)
try:
    print(len(x))
except TypeError as e:
    print("len", e)
try:
    print(x[0])
except TypeError as e:
    print("index", e)
try:
    x.append(1)
except AttributeError as e:
    print("append", e)
try:
    for v in x:
        print(v)
except TypeError as e:
    print("for", e)
try:
    print(sorted(x))
except TypeError as e:
    print("sorted", e)
try:
    print(sum(x))
except TypeError as e:
    print("sum", e)
try:
    print(list(x))
except TypeError as e:
    print("list", e)
try:
    print(1 in x)
except TypeError as e:
    print("in", e)
try:
    x[0] = 3
except TypeError as e:
    print("store", e)
try:
    del x[0]
except TypeError as e:
    print("del", e)
try:
    print(x[1:2])
except TypeError as e:
    print("slice", e)
try:
    print(list(reversed(x)))
except TypeError as e:
    print("reversed", e)
try:
    a, b = x
except TypeError as e:
    print("unpack", e)
try:
    print([*x])
except TypeError as e:
    print("star", e)
try:
    print(x.top())
except AttributeError as e:
    print("top", e)
try:
    print(max(x))
except TypeError as e:
    print("max", e)
try:
    print(tuple(x))
except TypeError as e:
    print("tuple", e)
try:
    print(x < [1])
except TypeError as e:
    print("lt", e)
