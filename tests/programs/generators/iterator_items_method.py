# for x in o.items() (keys(), values()) of an object whose method returns an iterator object
# or an object with __iter__ takes iter() of the result, which calls its __iter__, as for any
# object; a list it returns is iterated as it is
class It:
    def __init__(self, n: int) -> None:
        self.k = 0
        self.n = n

    def __iter__(self) -> "It":
        print("iter")
        return self

    def __next__(self) -> int:
        self.k += 1
        if self.k > self.n:
            raise StopIteration
        return self.k


class Bag:
    def __init__(self) -> None:
        self.xs = [7, 8]

    def __iter__(self):
        print("bag iter")
        return iter(self.xs)


class Store:
    def items(self) -> It:
        return It(2)

    def values(self) -> Bag:
        return Bag()

    def keys(self) -> list[str]:
        return ["a", "b"]


s = Store()
for x in s.items():
    print(x)
for v in s.values():
    print(v)
for k in s.keys():
    print(k)
print([x * 10 for x in s.items()])
