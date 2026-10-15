from typing import Callable

n = 2

def direct():
    global n
    if n > 0:
        n -= 1
        return direct()

print(direct(), n)
n = 2

def first():
    return second()

def second():
    global n
    if n > 0:
        n -= 1
        return first()

print(first(), n)
n = 2

def conditional():
    global n
    n -= 1
    return conditional() if n > 0 else None

print(conditional(), n)
n = 2
callback: Callable[[], None] = direct
print(callback(), n)

class Counter:
    def __init__(self, n: int):
        self.n = n

    def run(self):
        if self.n > 0:
            self.n -= 1
            return self.again()

    def again(self):
        return self.run()

c = Counter(2)
print(c.run(), c.n)

n = 2

def alias_call():
    global n
    if n > 0:
        n -= 1
        again = alias_call
        return again()

print(alias_call(), n)

n = 2

def known_value():
    global n
    if n == 0:
        return 1
    n -= 1
    return known_value() + 1

print(known_value(), n)
