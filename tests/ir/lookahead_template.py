# Templates first instantiated inside the look-ahead of an empty list and an empty dict: the
# loop reads each one before the statement that fills it, whose item expressions call
# templates no other code has called yet.
def twice(x):
    return x + x


def label(n):
    return "k" + str(n)


def main() -> None:
    xs = []
    d = {}
    for i in range(3):
        for v in xs:
            print("item", v)
        for k in d:
            print("key", k, d[k])
        xs.append(twice(i))
        d[label(i)] = twice(2.5)
    print(xs, d)


main()
