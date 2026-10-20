# A comprehension takes iter() of its iterator object again (CPython 3.13 inlines it), whatever
# its variable's name, also one spelled like the variables of the comprehensions the compiler
# makes of a call; sum(), list() and any() call __iter__ once.
class It:
    def __init__(self, n: int) -> None:
        self.k = 0
        self.n = n

    def __iter__(self):
        print("iter")
        return self

    def __next__(self):
        self.k += 1
        if self.k > self.n:
            raise StopIteration
        return self.k


print([__item for __item in It(2)])
print([y for y in It(2)])
print({__pys_item for __pys_item in It(2)})
print({__item0: 0 for __item0 in It(1)})
print([__items * 2 for __items in It(3) if __items != 2])


def f() -> list[int]:
    return [__item + 1 for __item in It(2)]


print(f())
print(sum(It(3)), list(It(2)), any(x > 1 for x in It(2)))
