# threading's Semaphore and BoundedSemaphore, as classes without annotations (#962): Sem's field
# holds a Cond, a class template whose field holds a Lock, and BSem's own __init__ is a class
# template too. BSem(3) derives from the specialization that its super().__init__(value) makes
# for an int, Sem(2)'s, whose objects therefore share a list with its own.
class Lock:
    def __init__(self) -> None:
        self.held = False


class Cond:
    def __init__(self, lock):
        self._lock = lock
        self.waiters = 0


class Sem:
    def __init__(self, value=1):
        self._cond = Cond(Lock())
        self._value = value

    def acquire(self) -> bool:
        self._value -= 1
        return self._cond._lock.held

    def release(self, n=1):
        self._value += n


class BSem(Sem):
    def __init__(self, value=1):
        super().__init__(value)
        self._initial = value

    def release(self, n=1):
        if self._value + n > self._initial:
            raise ValueError("Semaphore released too many times")
        super().release(n)


s = Sem(2)
b = BSem(3)
print(s.acquire(), s._value, b.acquire(), b._value, b._initial)
for x in [s, b]:
    x.release()
    print(x._value, x._cond.waiters, isinstance(x, BSem))
try:
    b.release()
except ValueError as e:
    print("ValueError:", e)
print(BSem()._initial, Sem()._value)
