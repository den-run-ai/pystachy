# more places exceptions come from and go to: methods and constructors, comprehensions, input()
# at the end of its input, a closed file, deleted variables, a raised KeyboardInterrupt, clauses
# in order, and an exception that leaves a for loop with an else block
import os
import tempfile


class Account:
    def __init__(self, owner: str, balance: int):
        if balance < 0:
            raise ValueError(f"negative balance for {owner}")
        self.owner = owner
        self.balance = balance

    def withdraw(self, n: int) -> int:
        if n > self.balance:
            raise RuntimeError(f"{self.owner} cannot withdraw {n}")
        self.balance -= n
        return self.balance


def open_all(specs: list[tuple[str, int]]) -> list[Account]:
    out: list[Account] = []
    for name, b in specs:
        try:
            out.append(Account(name, b))
        except ValueError as e:
            print("skipped:", e)
    return out


accounts = open_all([("ann", 10), ("bob", -5), ("cy", 3)])
for a in accounts:
    try:
        print(a.owner, a.withdraw(5))
    except RuntimeError as e:
        print("refused:", e)
try:
    squares = [int(s) ** 2 for s in ["1", "2", "three"]]
except ValueError as e:
    print("comprehension:", e)
try:
    line = input()
except EOFError as e:
    print("EOFError", repr(e))
d = tempfile.mkdtemp()
f = open(d + "/closed.txt", "w")
f.close()
try:
    f.write("x")
except ValueError as e:
    print("closed:", e)
os.remove(d + "/closed.txt")
os.rmdir(d)
v = 1
try:
    del v
    print(v)
except NameError as e:
    print("deleted:", e)
try:
    raise KeyboardInterrupt
except KeyboardInterrupt as e:
    print("raised KeyboardInterrupt caught", repr(e))
for exc in [IndexError("i"), KeyError("k"), LookupError("l"), ValueError("v")]:
    try:
        raise exc
    except IndexError:
        print("IndexError clause")
    except LookupError as e:
        print("LookupError clause", repr(e))
    except Exception as e:
        print("Exception clause", repr(e))
try:
    for i in range(3):
        if i == 2:
            raise StopIteration("no more")
    else:
        print("else not reached")
except StopIteration as e:
    print("left the loop:", e)
total = 0
while True:
    try:
        total += 1
        if total == 3:
            break
    finally:
        print("finally", total)
print("total", total)
