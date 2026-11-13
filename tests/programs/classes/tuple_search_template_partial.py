# A template __eq__ whose body compiles for some operands only: a tuple's in and count() call it
# for those (an object of its own class here) and decline the pairs it does not compile for,
# which this program never compares (#409)


class P:
    def __init__(self, n: int) -> None:
        self.n = n

    def __eq__(self, other: object) -> bool:
        if isinstance(other, P):
            return self.n == other.n
        return other.missing()


class Q:
    pass


def search(x: P | Q, y: P | Q) -> bool:
    return x in (y,)


def count(x: P | Q, y: P | Q) -> int:
    return (y, y, x).count(x)


print(search(P(1), P(1)), search(P(1), P(2)), search(Q(), Q()))
print(count(P(3), P(3)), count(P(3), P(4)))
q = Q()
print(search(q, q), count(q, q))
